import operator
from typing import Annotated, Any

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent


class TaskOption(BaseModel):
    description: str = Field(default="", description="タスクオプションの説明")


class Task(BaseModel):
    task_name: str = Field(..., description="タスクの名前")
    options: list[TaskOption] = Field(
        default_factory=list,
        min_items=2,
        max_items=3,
        description="2~3個のタスクオプション",
    )


class DecomposedTasks(BaseModel):
    values: list[Task] = Field(
        default_factory=list,
        min_items=3,
        max_items=5,
        description="3~5個に分解されたタスク",
    )


class TaskExecutionState(BaseModel):
    original_query: str = Field(..., description="ユーザーの初期クエリ")
    tasks: DecomposedTasks = Field(
        default_factory=DecomposedTasks,
        description="複数のオプションを持つタスクのリスト",
    )
    current_task_index: int = Field(default=0, description="現在のタスクのインデックス")
    chosen_options: Annotated[list[int], operator.add] = Field(
        default_factory=list, description="各タスクの選択されたオプションのインデックス"
    )
    results: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="実行されたタスクの結果"
    )
    final_output: str = Field(default="", description="最終的な集約出力")


class QueryDecomposer:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm.with_structured_output(DecomposedTasks)

    def run(self, query: str) -> DecomposedTasks:
        prompt = ChatPromptTemplate.from_template(
            "タスク: 以下のクエリを3〜5個の高レベルタスクに分解し、各タスクに2〜3個の具体的なオプションを提供してください。\n"
            "要件:\n"
            "1. 各高レベルタスクは明確な目的を持つこと。\n"
            "2. 各タスクに2〜3個の異なるアプローチまたはオプションを提供すること。\n"
            "3. タスクは論理的な順序で並べること。\n"
            "4. 各タスクとオプションは動詞で始めること。\n"
            "5. タスクは日本語で出力すること。\n\n"
            "クエリ: {query}"
        )
        chain = prompt | self.llm
        return chain.invoke({"query": query})


class OptionPresenter:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(self, task: Task) -> int:
        task_name = task.task_name
        options = task.options

        print(f"\nタスク: {task_name}")
        for i, option in enumerate(options):
            print(f"{i + 1}. {option.description}")

        choice_prompt = ChatPromptTemplate.from_template(
            "タスク: 与えられたタスクとオプションに基づいて、最適なオプションを選択してください。必ず番号のみで回答してください。\n"
            "タスク: {task_name}\n"
            "オプション:\n{options_text}\n"
            "選択 (1-{num_options}): "
        )

        options_text = "\n".join(
            f"{i+1}. {option.description}" for i, option in enumerate(options)
        )
        chain = choice_prompt | self.llm | StrOutputParser()
        choice_str = chain.invoke(
            {
                "task_name": task_name,
                "options_text": options_text,
                "num_options": len(options),
            }
        )
        print(f"==> エージェントの選択: {choice_str}\n")

        return int(choice_str.strip()) - 1


class TaskExecutor:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.tools = [TavilySearchResults(max_results=3)]

    def run(self, task: Task, chosen_option: TaskOption) -> str:
        agent = create_react_agent(self.llm, self.tools)
        result = agent.invoke(
            {
                "messages": [
                    (
                        "human",
                        f"以下のタスクを実行し、詳細な回答を提供してください:\n\n"
                        f"タスク: {task.task_name}\n"
                        f"選択されたアプローチ: {chosen_option.description}\n\n"
                        f"要件:\n"
                        f"1. 必要に応じて提供されたツールを使用すること。\n"
                        f"2. 実行において徹底的かつ包括的であること。\n"
                        f"3. 可能な限り具体的な事実やデータを提供すること。\n"
                        f"4. 発見事項を明確にまとめること。\n",
                    )
                ]
            }
        )
        return result["messages"][-1].content


class ResultAggregator:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(
        self,
        original_query: str,
        tasks: list[Task],
        chosen_options: list[int],
        results: list[str],
    ) -> str:
        prompt = ChatPromptTemplate.from_template(
            "タスク: 以下の情報に基づいて、包括的で一貫性のある回答を作成してください。\n"
            "要件:\n"
            "1. 提供されたすべての情報を適切な構成で総合すること。\n"
            "2. 回答が元のクエリに直接対応していることを確認すること。\n"
            "3. 実行された各タスクからの主要なポイントと発見事項を含めること。\n"
            "4. 各タスクで選択されたアプローチを強調すること。\n"
            "5. 最後に結論またはまとめを提供すること。\n"
            "6. 回答は詳細かつ簡潔で、300〜350語程度を目指すこと。\n"
            "7. 回答は日本語で行うこと。\n\n"
            "元のクエリ: {original_query}\n\n"
            "実行されたタスクと結果:\n{task_results}\n\n"
            "総合的な回答:"
        )

        task_results = self._format_task_results(tasks, chosen_options, results)
        chain = prompt | self.llm | StrOutputParser()
        return chain.invoke(
            {
                "original_query": original_query,
                "task_results": task_results,
            }
        )

    @staticmethod
    def _format_task_results(
        tasks: list[Task], chosen_options: list[int], results: list[str]
    ) -> str:
        task_results = ""
        for i, (task, chosen_option, result) in enumerate(
            zip(tasks, chosen_options, results)
        ):
            task_name = task.task_name
            chosen_option_desc = task.options[chosen_option].description
            task_results += f"タスク {i+1}: {task_name}\n"
            task_results += f"選択されたアプローチ: {chosen_option_desc}\n"
            task_results += f"結果: {result}\n\n"
        return task_results


class MultiPathPlanGeneration:
    def __init__(
        self,
        llm: ChatOpenAI,
    ):
        self.query_decomposer = QueryDecomposer(llm=llm)
        self.option_presenter = OptionPresenter(llm=llm)
        self.task_executor = TaskExecutor(llm=llm)
        self.result_aggregator = ResultAggregator(llm=llm)
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        graph = StateGraph(TaskExecutionState)

        graph.add_node("decompose_query", self._decompose_query)
        graph.add_node("present_options", self._present_options)
        graph.add_node("execute_task", self._execute_task)
        graph.add_node("aggregate_results", self._aggregate_results)

        graph.set_entry_point("decompose_query")

        graph.add_edge("decompose_query", "present_options")
        graph.add_edge("present_options", "execute_task")
        graph.add_conditional_edges(
            "execute_task",
            lambda state: state.current_task_index < len(state.tasks.values),
            {True: "present_options", False: "aggregate_results"},
        )
        graph.add_edge("aggregate_results", END)

        return graph.compile()

    def _decompose_query(self, state: TaskExecutionState) -> dict[str, Any]:
        tasks = self.query_decomposer.run(state.original_query)
        return {"tasks": tasks}

    def _present_options(self, state: TaskExecutionState) -> dict[str, Any]:
        current_task = state.tasks.values[state.current_task_index]
        chosen_option = self.option_presenter.run(current_task)
        return {"chosen_options": [chosen_option]}

    def _execute_task(self, state: TaskExecutionState) -> dict[str, Any]:
        current_task = state.tasks.values[state.current_task_index]
        chosen_option = current_task.options[state.chosen_options[-1]]
        result = self.task_executor.run(current_task, chosen_option)
        return {
            "results": [result],
            "current_task_index": state.current_task_index + 1,
        }

    def _aggregate_results(self, state: TaskExecutionState) -> dict[str, Any]:
        final_output = self.result_aggregator.run(
            state.original_query,
            state.tasks.values,
            state.chosen_options,
            state.results,
        )
        return {"final_output": final_output}

    def run(self, query: str) -> str:
        initial_state = TaskExecutionState(original_query=query)
        final_state = self.graph.invoke(initial_state, {"recursion_limit": 1000})
        return final_state.get("final_output", "最終的な回答の生成に失敗しました。")


def main():
    import argparse

    from settings import Settings

    settings = Settings()

    parser = argparse.ArgumentParser(
        description="MultiPathPlanGenerationを使用してタスクを実行します"
    )
    parser.add_argument("--task", type=str, required=True, help="実行するタスク")
    args = parser.parse_args()

    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    agent = MultiPathPlanGeneration(llm=llm)
    result = agent.run(args.task)
    print("\n=== 最終出力 ===")
    print(result)


if __name__ == "__main__":
    main()
