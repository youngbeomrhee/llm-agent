import operator
from typing import Annotated, Any

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from passive_goal_creator.main import Goals, PassiveGoalCreator
from prompt_optimiser.main import OptimisedGoal, OptimisedGoals, PromptOptimiser


class TaskExecutionState(BaseModel):
    original_query: str = Field(..., description="ユーザーが最初に入力したクエリ")
    tasks: OptimisedGoals = Field(
        default_factory=lambda: OptimisedGoals(), description="実行するタスクのリスト"
    )
    current_task_index: int = Field(default=0, description="現在実行中のタスクの番号")
    results: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="実行済みタスクの結果リスト"
    )
    final_output: str = Field(default="", description="最終的な出力結果")


class QueryDecomposer:
    def __init__(self, llm: ChatOpenAI):
        self.passive_goal_creator = PassiveGoalCreator(llm=llm)
        self.prompt_optimiser = PromptOptimiser(llm=llm)

    def run(self, query: str) -> OptimisedGoals:
        goals: Goals = self.passive_goal_creator.run(user_input=query)
        return self.prompt_optimiser.run(goals=goals)


class TaskExecutor:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.tools = [TavilySearchResults(max_results=3)]

    def run(self, task: OptimisedGoal) -> str:
        agent = create_react_agent(self.llm, self.tools)
        result = agent.invoke(self._create_task_message(task))
        return result["messages"][-1].content

    @staticmethod
    def _create_task_message(task: OptimisedGoal) -> dict[str, Any]:
        return {
            "messages": [
                (
                    "human",
                    f"次のタスクを実行し、詳細な回答を提供してください。\n\nタスク: {task.text}\n\n"
                    "要件:\n"
                    "1. 必要に応じて提供されたツールを使用してください。\n"
                    "2. 実行は徹底的かつ包括的に行ってください。\n"
                    "3. 可能な限り具体的な事実やデータを提供してください。\n"
                    "4. 発見した内容を明確に要約してください。\n",
                )
            ]
        }


class ResultAggregator:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(self, original_query: str, results: list[str]) -> str:
        prompt = self._create_aggregation_prompt()
        chain = prompt | self.llm | StrOutputParser()
        return chain.invoke(self._create_aggregation_input(original_query, results))

    @staticmethod
    def _create_aggregation_prompt() -> ChatPromptTemplate:
        return ChatPromptTemplate.from_template(
            "タスク: 以下の情報に基づいて、包括的で一貫性のある回答を作成してください。\n"
            "要件:\n"
            "1. 提供されたすべての情報を統合し、よく構成された回答にしてください。\n"
            "2. 回答は元のクエリに直接応える形にしてください。\n"
            "3. 各情報の重要なポイントや発見を含めてください。\n"
            "4. 最後に結論や要約を提供してください。\n"
            "5. 回答は詳細でありながら簡潔にし、250〜300語程度を目指してください。\n"
            "6. 回答は日本語で行ってください。\n\n"
            "Original Query: {original_query}\n\n"
            "Information:\n{results}\n\n"
            "Synthesized Response:"
        )

    @staticmethod
    def _create_aggregation_input(
        original_query: str, results: list[str]
    ) -> dict[str, Any]:
        return {
            "original_query": original_query,
            "results": "\n\n".join(
                f"Info {i+1}:\n{result}" for i, result in enumerate(results)
            ),
        }


class SinglePathPlanGeneration:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.query_decomposer = QueryDecomposer(llm=self.llm)
        self.task_executor = TaskExecutor(llm=self.llm)
        self.result_aggregator = ResultAggregator(llm=self.llm)
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        graph = StateGraph(TaskExecutionState)
        graph.add_node("decompose_query", self._decompose_query)
        graph.add_node("execute_task", self._execute_task)
        graph.add_node("aggregate_results", self._aggregate_results)
        graph.set_entry_point("decompose_query")
        graph.add_edge("decompose_query", "execute_task")
        graph.add_conditional_edges(
            "execute_task",
            lambda state: state.current_task_index < len(state.tasks.goals),
            {True: "execute_task", False: "aggregate_results"},
        )
        graph.add_edge("aggregate_results", END)
        return graph.compile()

    def _decompose_query(self, state: TaskExecutionState) -> dict[str, Any]:
        optimised_goals = self.query_decomposer.run(state.original_query)
        return {"tasks": optimised_goals}

    def _execute_task(self, state: TaskExecutionState) -> dict[str, Any]:
        current_task = state.tasks.goals[state.current_task_index]
        result = self.task_executor.run(current_task)
        return {
            "results": [result],
            "current_task_index": state.current_task_index + 1,
        }

    def _aggregate_results(self, state: TaskExecutionState) -> dict[str, Any]:
        final_output = self.result_aggregator.run(state.original_query, state.results)
        return {"final_output": final_output}

    def run(self, query: str) -> str:
        initial_state = TaskExecutionState(original_query=query)
        final_state = self.graph.invoke(initial_state, {"recursion_limit": 1000})
        return final_state.get("final_output", "Failed to generate a final response.")


def main():
    import argparse

    from settings import Settings

    settings = Settings()

    parser = argparse.ArgumentParser(
        description="SinglePathPlanGenerationを使用してタスクを実行します"
    )
    parser.add_argument("--task", type=str, required=True, help="実行するタスク")
    args = parser.parse_args()

    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    agent = SinglePathPlanGeneration(llm=llm)
    result = agent.run(args.task)
    print(result)


if __name__ == "__main__":
    main()
