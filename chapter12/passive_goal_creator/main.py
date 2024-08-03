from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI


class Goal(BaseModel):
    description: str = Field(..., description="目標の説明")

    @property
    def text(self) -> str:
        return f"{self.description}"


class Goals(BaseModel):
    goals: list[Goal] = Field(default=[], description="目標のリスト")

    @property
    def text(self) -> str:
        return "\n".join([goal.text for goal in self.goals])


class PassiveGoalCreator:
    def __init__(
        self,
        llm: ChatOpenAI,
    ):
        self.llm = llm.with_structured_output(Goals)

        self.prompt = ChatPromptTemplate.from_template(
            "ユーザーの入力を分析し、明確で実行可能な目標を生成してください。\n"
            "要件:\n"
            "1. 各目標は具体的かつ明確であり、実行可能なレベルで詳細化されている必要があります。\n"
            "2. 3-5個の目標を生成してください。\n"
            "ユーザーの入力: {user_input}\n\n"
            "生成された目標:"
        )
        self.chain = self.prompt | self.llm

    def run(self, user_input: str) -> Goals:
        return self.chain.invoke({"user_input": user_input})


def main():
    import argparse

    from settings import Settings

    settings = Settings()

    parser = argparse.ArgumentParser(
        description="PassiveGoalCreatorを利用して目標のリストを生成します"
    )
    parser.add_argument("--task", type=str, required=True, help="実行するタスク")
    args = parser.parse_args()

    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    agent = PassiveGoalCreator(llm=llm)
    result: Goals = agent.run(args.task)

    for index, goal in enumerate(result.goals, start=1):
        print(f"目標{index}: {goal.text}")


if __name__ == "__main__":
    main()
