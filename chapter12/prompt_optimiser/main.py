from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from passive_goal_creator.main import Goals, PassiveGoalCreator


class OptimisedGoal(BaseModel):
    description: str = Field(..., description="目標の説明")
    metrics: str = Field(..., description="目標の達成度を測定する方法")

    @property
    def text(self) -> str:
        return f"{self.description}(測定基準: {self.metrics})"


class OptimisedGoals(BaseModel):
    goals: list[OptimisedGoal] = Field(
        default=[], description="最適化された目標のリスト"
    )

    @property
    def text(self) -> str:
        return "\n".join([goal.text for goal in self.goals])


class PromptOptimiser:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm.with_structured_output(OptimisedGoals)

        self.prompt = ChatPromptTemplate.from_template(
            "以下の目標リストを最適化してください。各目標をより具体的、測定可能、達成可能、関連性が高いものに水平思考で改善してください。\n"
            "元の目標リスト:\n"
            "{goals}\n\n"
            "最適化された目標リスト:"
        )
        self.chain = self.prompt | self.llm

    def run(self, goals: Goals) -> OptimisedGoals:
        return self.chain.invoke({"goals": goals.text})


def main():
    import argparse

    from settings import Settings

    settings = Settings()

    parser = argparse.ArgumentParser(
        description="PromptOptimiserを利用して、生成された目標のリストを最適化します"
    )
    parser.add_argument("--task", type=str, required=True, help="実行するタスク")
    args = parser.parse_args()

    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )

    passive_goal_creator = PassiveGoalCreator(llm=llm)
    goals: Goals = passive_goal_creator.run(args.task)

    prompt_optimiser = PromptOptimiser(llm=llm)
    optimised_goals: OptimisedGoals = prompt_optimiser.run(goals=goals)

    for index, goal in enumerate(optimised_goals.goals, start=1):
        print(f"目標{index}: {goal.text}")


if __name__ == "__main__":
    main()
