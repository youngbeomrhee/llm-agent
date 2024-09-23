from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class Goal(BaseModel):
    description: str = Field(..., description="目標の説明")

    @property
    def text(self) -> str:
        return f"{self.description}"


class PassiveGoalCreator:
    def __init__(
        self,
        llm: ChatOpenAI,
    ):
        self.llm = llm.with_structured_output(Goal)

        self.prompt = ChatPromptTemplate.from_template(
            "ユーザーの入力を分析し、明確で実行可能な目標を生成してください。\n"
            "要件:\n"
            "1. 目標は具体的かつ明確であり、実行可能なレベルで詳細化されている必要があります。\n"
            "2. あなたが実行可能な行動は以下の行動だけです。\n"
            "   - インターネットを利用して、目標を達成するための調査を行う。\n"
            "   - ユーザーのためのレポートを生成する。\n"
            "3. 決して2.以外の行動を取ってはいけません。\n"
            "ユーザーの入力: {query}\n\n"
            "生成された目標:"
        )
        self.chain = self.prompt | self.llm

    def run(self, query: str) -> Goal:
        return self.chain.invoke({"query": query})


def main():
    import argparse

    from settings import Settings

    settings = Settings()

    parser = argparse.ArgumentParser(
        description="PassiveGoalCreatorを利用して目標を生成します"
    )
    parser.add_argument("--task", type=str, required=True, help="実行するタスク")
    args = parser.parse_args()

    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    goal_creator = PassiveGoalCreator(llm=llm)
    result: Goal = goal_creator.run(query=args.task)

    print(f"生成された目標: {result.text}")


if __name__ == "__main__":
    main()
