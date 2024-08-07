import operator
from datetime import datetime
from typing import Annotated, Any

from common.reflection_manager import Reflection, ReflectionManager, TaskReflector
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent


def format_reflections(reflections: list[Reflection]) -> str:
    return (
        "\n\n".join(
            f"<ref_{i}><task>{r.task}</task><reflection>{r.reflection}</reflection></ref_{i}>"
            for i, r in enumerate(reflections)
        )
        if reflections
        else "No relevant past reflections."
    )


class DecomposedTasks(BaseModel):
    values: list[str] = Field(
        default_factory=list,
        min_items=3,
        max_items=5,
        description="3~5個に分解されたタスク",
    )


class TaskExecutionState(BaseModel):
    original_query: str = Field(..., description="ユーザーが最初に入力したクエリ")
    tasks: DecomposedTasks = Field(
        default_factory=DecomposedTasks, description="実行するタスクのリスト"
    )
    current_task_index: int = Field(default=0, description="現在実行中のタスクの番号")
    results: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="実行済みタスクの結果リスト"
    )
    reflection_ids: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="リフレクション結果のIDリスト"
    )
    final_output: str = Field(default="", description="最終的な出力結果")
    retry_count: int = Field(default=0, description="タスクの再試行回数")


class QueryDecomposer:
    def __init__(self, llm: ChatOpenAI, reflection_manager: ReflectionManager):
        self.llm = llm.with_structured_output(DecomposedTasks)
        self.reflection_manager = reflection_manager
        self.current_date = datetime.now().strftime("%Y-%m-%d")

    def run(self, query: str) -> DecomposedTasks:
        relevant_reflections = self.reflection_manager.get_relevant_reflections(query)
        reflection_text = format_reflections(relevant_reflections)
        prompt = self._create_decomposition_prompt()
        chain = prompt | self.llm
        tasks = chain.invoke({"query": query, "reflections": reflection_text})
        return tasks

    def _create_decomposition_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_template(
            f"CURRENT_DATE: {self.current_date}\n"
            "-----\n"
            "タスク: 次のクエリを具体的で実行可能なタスクに分解してください。\n"
            "要件:\n"
            "1. 各タスクは単一で明確な指示であること。\n"
            "2. タスクは実行の論理的な順序でリスト化すること。\n"
            "3. 3から5つのタスクを提供すること。\n"
            "4. 各タスクは動詞で始めること。\n"
            "5. タスクに番号を付けないこと。\n"
            "6. タスクを作成する際に以下の過去のふりかえりを考慮すること:\n{reflections}\n\n"
            "Query: {query}"
        )


class TaskExecutor:
    def __init__(self, llm: ChatOpenAI, reflection_manager: ReflectionManager):
        self.llm = llm
        self.reflection_manager = reflection_manager
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.tools = [TavilySearchResults(max_results=3)]

    def run(self, task: str) -> str:
        relevant_reflections = self.reflection_manager.get_relevant_reflections(task)
        reflection_text = format_reflections(relevant_reflections)
        agent = create_react_agent(self.llm, self.tools)
        result = agent.invoke(self._create_task_message(task, reflection_text))
        return result["messages"][-1].content

    def _create_task_message(self, task: str, reflection_text: str) -> dict[str, Any]:
        return {
            "messages": [
                (
                    "human",
                    f"CURRENT_DATE: {self.current_date}\n"
                    "-----\n"
                    f"次のタスクを実行し、詳細な回答を提供してください。\n\nタスク: {task}\n\n"
                    "要件:\n"
                    "1. 必要に応じて提供されたツールを使用すること。\n"
                    "2. 実行において徹底的かつ包括的であること。\n"
                    "3. 可能な限り具体的な事実やデータを提供すること。\n"
                    "4. 発見事項を明確に要約すること。\n"
                    f"5. 以下の過去のふりかえりを考慮すること:\n{reflection_text}\n",
                )
            ]
        }


class ResultAggregator:
    def __init__(self, llm: ChatOpenAI, reflection_manager: ReflectionManager):
        self.llm = llm
        self.reflection_manager = reflection_manager
        self.current_date = datetime.now().strftime("%Y-%m-%d")

    def run(
        self, original_query: str, results: list[str], reflection_ids: list[str]
    ) -> str:
        reflections = [
            self.reflection_manager.get_reflection(rid) for rid in reflection_ids
        ]
        prompt = self._create_aggregation_prompt()
        chain = prompt | self.llm | StrOutputParser()
        return chain.invoke(
            self._create_aggregation_input(original_query, results, reflections)
        )

    def _create_aggregation_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_template(
            f"CURRENT_DATE: {self.current_date}\n"
            "-----\n"
            "タスク: 以下の情報に基づいて、包括的で一貫性のある回答を作成してください。\n"
            "要件:\n"
            "1. 提供されたすべての情報を統合し、よく構成された回答にすること。\n"
            "2. 回答が元のクエリに直接対応していることを確認すること。\n"
            "3. 各情報の重要なポイントや発見事項を含めること。\n"
            "4. 最後に結論や要約を提供すること。\n"
            "5. 回答は詳細でありながら簡潔であり、250〜300語程度を目指すこと。\n"
            "6. 回答は必ず日本語で行うこと。\n\n"
            "Original Query: {original_query}\n\n"
            "Information:\n{results}\n\n"
            "Self-reflections:\n{reflections}\n\n"
            "Synthesized Response:"
        )

    @staticmethod
    def _create_aggregation_input(
        original_query: str, results: list[str], reflections: list[Reflection]
    ) -> dict[str, Any]:
        return {
            "original_query": original_query,
            "results": "\n\n".join(
                f"Info {i+1}:\n{result}" for i, result in enumerate(results)
            ),
            "reflections": "\n\n".join(
                f"Reflection {i+1}:\n{reflection.reflection}\nJudgment: {reflection.judgment}"
                for i, reflection in enumerate(reflections)
            ),
        }


class ReflectiveAgent:
    def __init__(
        self,
        llm: ChatOpenAI,
        reflection_manager: ReflectionManager,
        task_reflector: TaskReflector,
        max_retries: int = 2,
    ):
        self.llm = llm
        self.reflection_manager = reflection_manager
        self.task_reflector = task_reflector
        self.query_decomposer = QueryDecomposer(
            llm=self.llm, reflection_manager=self.reflection_manager
        )
        self.task_executor = TaskExecutor(
            llm=self.llm, reflection_manager=self.reflection_manager
        )
        self.result_aggregator = ResultAggregator(
            llm=self.llm, reflection_manager=self.reflection_manager
        )
        self.max_retries = max_retries
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        graph = StateGraph(TaskExecutionState)
        graph.add_node("decompose_query", self._decompose_query)
        graph.add_node("execute_task", self._execute_task)
        graph.add_node("reflect_on_task", self._reflect_on_task)
        graph.add_node("update_task_index", self._update_task_index)
        graph.add_node("aggregate_results", self._aggregate_results)
        graph.set_entry_point("decompose_query")
        graph.add_edge("decompose_query", "execute_task")
        graph.add_edge("execute_task", "reflect_on_task")
        graph.add_conditional_edges(
            "reflect_on_task",
            self._should_retry_or_continue,
            {
                "retry": "execute_task",
                "continue": "update_task_index",
                "finish": "aggregate_results",
            },
        )
        graph.add_edge("update_task_index", "execute_task")
        graph.add_edge("aggregate_results", END)
        return graph.compile()

    def _decompose_query(self, state: TaskExecutionState) -> dict[str, Any]:
        tasks = self.query_decomposer.run(state.original_query)
        return {"tasks": tasks}

    def _execute_task(self, state: TaskExecutionState) -> dict[str, Any]:
        current_task = state.tasks.values[state.current_task_index]
        result = self.task_executor.run(current_task)
        return {"results": [result], "current_task_index": state.current_task_index}

    def _reflect_on_task(self, state: TaskExecutionState) -> dict[str, Any]:
        current_task = state.tasks.values[state.current_task_index]
        current_result = state.results[-1]
        reflection = self.task_reflector.run(current_task, current_result)
        return {
            "reflection_ids": [reflection.id],
            "retry_count": (
                state.retry_count + 1 if reflection.judgment.needs_retry else 0
            ),
        }

    def _should_retry_or_continue(self, state: TaskExecutionState) -> str:
        latest_reflection_id = state.reflection_ids[-1]
        latest_reflection = self.reflection_manager.get_reflection(latest_reflection_id)
        if (
            latest_reflection
            and latest_reflection.judgment.needs_retry
            and state.retry_count < self.max_retries
        ):
            return "retry"
        elif state.current_task_index < len(state.tasks.values) - 1:
            return "continue"
        else:
            return "finish"

    def _update_task_index(self, state: TaskExecutionState) -> dict[str, Any]:
        return {"current_task_index": state.current_task_index + 1}

    def _aggregate_results(self, state: TaskExecutionState) -> dict[str, Any]:
        final_output = self.result_aggregator.run(
            state.original_query, state.results, state.reflection_ids
        )
        return {"final_output": final_output}

    def run(self, query: str) -> str:
        initial_state = TaskExecutionState(original_query=query)
        final_state = self.graph.invoke(initial_state, {"recursion_limit": 1000})
        return final_state.get("final_output", "エラー: 出力に失敗しました。")


def main():
    import argparse

    from settings import Settings

    settings = Settings()

    parser = argparse.ArgumentParser(
        description="ReflectiveAgentを使用してタスクを実行します（Self-reflection）"
    )
    parser.add_argument("--task", type=str, required=True, help="実行するタスク")
    args = parser.parse_args()

    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    reflection_manager = ReflectionManager(file_path="tmp/self_reflection_db.json")
    task_reflector = TaskReflector(llm=llm, reflection_manager=reflection_manager)
    agent = ReflectiveAgent(
        llm=llm, reflection_manager=reflection_manager, task_reflector=task_reflector
    )
    result = agent.run(args.task)
    print(result)


if __name__ == "__main__":
    main()
