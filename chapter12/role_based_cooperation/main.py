from typing import Any

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from passive_goal_creator.main import Goals, PassiveGoalCreator
from prompt_optimiser.main import OptimisedGoals, PromptOptimiser


class Role(BaseModel):
    """タスクに割り当てられる役割を表すクラス"""

    name: str = Field(..., description="役割の名前")
    description: str = Field(..., description="役割の詳細な説明")
    key_skills: list[str] = Field(
        ..., description="この役割に必要な主要なスキルやアトリビュート"
    )


class Task(BaseModel):
    """実行すべきタスクを表すクラス"""

    description: str = Field(..., description="タスクの説明")
    role: Role = Field(default=None, description="タスクに割り当てられた役割")


class TasksWithRoles(BaseModel):
    """役割が割り当てられたタスクのリストを表すクラス"""

    tasks: list[Task] = Field(..., description="役割が割り当てられたタスクのリスト")


class AgentState(BaseModel):
    """エージェントの状態を表すクラス"""

    query: str = Field(..., description="ユーザーからの元のクエリ")
    tasks: list[Task] = Field(
        default_factory=list, description="実行すべきタスクのリスト"
    )
    results: dict[str, str] = Field(
        default_factory=dict, description="完了したタスクの結果"
    )
    current_task_index: int = Field(
        default=0, description="現在実行中のタスクのインデックス"
    )
    final_report: str = Field(default="", description="最終的に生成されたレポート")


class QueryDecomposer:
    def __init__(self, llm: ChatOpenAI):
        self.passive_goal_creator = PassiveGoalCreator(llm=llm)
        self.prompt_optimiser = PromptOptimiser(llm=llm)

    def run(self, query: str) -> OptimisedGoals:
        goals: Goals = self.passive_goal_creator.run(user_input=query)
        return self.prompt_optimiser.run(goals=goals)


class RoleGenerator:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm.with_structured_output(TasksWithRoles)

    def run(self, tasks: list[Task]) -> list[Task]:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "あなたは創造的な役割設計の専門家です。与えられたタスクに対して、ユニークで適切な役割を生成してください。",
                ),
                (
                    "human",
                    """タスク: {tasks}

これらのタスクに対して、以下の指示に従って役割を割り当ててください：

1. 各タスクに対して、独自の創造的な役割を考案してください。既存の職業名や一般的な役割名にとらわれる必要はありません。
2. 役割名は、そのタスクの本質を反映した魅力的で記憶に残るものにしてください。
3. 各役割に対して、その役割がなぜそのタスクに最適なのかを説明する詳細な説明を提供してください。
4. その役割が効果的にタスクを遂行するために必要な主要なスキルやアトリビュートを3つ挙げてください。

創造性を発揮し、タスクの本質を捉えた革新的な役割を生成してください。""",
                ),
            ]
        )
        chain = prompt | self.llm
        tasks_with_roles = chain.invoke(
            {"tasks": "\n".join([task.description for task in tasks])}
        )
        return tasks_with_roles.tasks


class Executor:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.tools = [TavilySearchResults(max_results=3)]
        self.base_agent = create_react_agent(self.llm, self.tools)

    def run(self, task: Task) -> str:
        system_message = SystemMessage(
            content=f"""あなたは{task.role.name}です。
説明: {task.role.description}
主要なスキル: {', '.join(task.role.key_skills)}

あなたの役割に基づいて、与えられたタスクを最高の能力で遂行してください。"""
        )

        result = self.base_agent.invoke(
            {
                "messages": [
                    system_message,
                    HumanMessage(
                        content=f"以下のタスクを実行してください：\n\n{task.description}"
                    ),
                ]
            }
        )
        return result["messages"][-1].content


class Reporter:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(self, query: str, results: dict[str, str]) -> str:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "あなたは総合的なレポート作成の専門家です。複数の情報源からの結果を統合し、洞察力に富んだ包括的なレポートを作成する能力があります。",
                ),
                (
                    "human",
                    """クエリ: {query}

各タスクの結果:
{results}

上記の情報を基に、以下の指示に従って詳細なレポートを作成してください：

1. クエリに直接答える形で開始し、重要なポイントを簡潔に要約してください。
2. 各タスクの結果を統合し、一貫性のある物語を作成してください。
3. データや具体的な例を用いて主張を裏付けてください。
4. 異なる視点や対立する情報がある場合は、それらを公平に提示してください。
5. 適切な場合は、結果から導き出される洞察や推奨事項を含めてください。
6. レポートの最後に、主要な発見や結論を簡潔にまとめてください。

レポートは論理的に構造化され、読みやすく、情報量が豊富であることを心がけてください。""",
                ),
            ]
        )
        chain = prompt | self.llm | StrOutputParser()
        return chain.invoke(
            {
                "query": query,
                "results": "\n".join(
                    [f"タスク: {k}\n結果: {v}\n" for k, v in results.items()]
                ),
            }
        )


class RoleBasedCooperation:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.query_decomposer = QueryDecomposer(llm=llm)
        self.role_generator = RoleGenerator(llm=llm)
        self.executor = Executor(llm=llm)
        self.reporter = Reporter(llm=llm)
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("planner", self._plan_tasks)
        workflow.add_node("role_assigner", self._assign_roles)
        workflow.add_node("executor", self._execute_task)
        workflow.add_node("reporter", self._generate_report)

        workflow.set_entry_point("planner")

        workflow.add_edge("planner", "role_assigner")
        workflow.add_conditional_edges(
            "role_assigner",
            lambda state: state.current_task_index < len(state.tasks),
            {True: "executor", False: "reporter"},
        )
        workflow.add_conditional_edges(
            "executor",
            lambda state: state.current_task_index < len(state.tasks),
            {True: "executor", False: "reporter"},
        )

        workflow.add_edge("reporter", END)

        return workflow.compile()

    def _plan_tasks(self, state: AgentState) -> dict[str, Any]:
        optimised_goals = self.query_decomposer.run(state.query)
        tasks = [Task(description=goal.text) for goal in optimised_goals.goals]
        return {"tasks": tasks}

    def _assign_roles(self, state: AgentState) -> dict[str, Any]:
        tasks_with_roles = self.role_generator.run(state.tasks)
        return {"tasks": tasks_with_roles}

    def _execute_task(self, state: AgentState) -> dict[str, Any]:
        current_task = state.tasks[state.current_task_index]
        result = self.executor.run(current_task)
        new_results = state.results.copy()
        new_results[current_task.description] = result
        return {
            "results": new_results,
            "current_task_index": state.current_task_index + 1,
        }

    def _generate_report(self, state: AgentState) -> dict[str, Any]:
        report = self.reporter.run(state.query, state.results)
        return {"final_report": report}

    def run(self, query: str) -> str:
        initial_state = AgentState(query=query)
        final_state = self.graph.invoke(initial_state, {"recursion_limit": 1000})
        return final_state["final_report"]


def main():
    import argparse

    from settings import Settings

    settings = Settings()
    parser = argparse.ArgumentParser(
        description="RoleBasedCooperationを使用してタスクを実行します"
    )
    parser.add_argument("--task", type=str, required=True, help="実行するタスク")
    args = parser.parse_args()

    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    agent = RoleBasedCooperation(llm=llm)
    result = agent.run(args.task)
    print(result)


if __name__ == "__main__":
    main()
