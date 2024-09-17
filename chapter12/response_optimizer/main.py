from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from passive_goal_creator.main import Goal, PassiveGoalCreator
from prompt_optimizer.main import OptimizedGoal, PromptOptimizer


class ResponseOptimizer:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "あなたは高度なAIシステムのレスポンス最適化スペシャリストです。与えられた目標に対して、AIシステムが最も効果的にレスポンスを返すための戦略を設計してください。",
                ),
                (
                    "human",
                    "以下の手順に従って、レスポンス最適化プロンプトを作成してください：\n\n"
                    "1. 目標分析:\n"
                    "提示された目標を分析し、主要な要素や意図を特定してください。\n\n"
                    "2. レスポンス戦略の設計:\n"
                    "目標達成のための最適なレスポンス戦略を考案してください。トーン、構造、内容の焦点などを考慮に入れてください。\n\n"
                    "3. 具体的な指示の作成:\n"
                    "AIシステムに対する明確で実行可能な指示を作成してください。必要に応じて、箇条書きや番号付きリストを使用してください。\n\n"
                    "4. 例の提供:\n"
                    "可能であれば、目標に沿ったレスポンスの例を1つ以上含めてください。\n\n"
                    "5. 評価基準の設定:\n"
                    "レスポンスの効果を測定するための基準を定義してください。\n\n"
                    "以下の構造でレスポンス最適化プロンプトを出力してください:\n\n"
                    "目標分析:\n"
                    "[ここに目標の分析結果を記入]\n\n"
                    "レスポンス戦略:\n"
                    "[ここに設計されたレスポンス戦略を記入]\n\n"
                    "AIシステムへの指示:\n"
                    "[ここにAIシステムへの具体的な指示を記入]\n\n"
                    "レスポンス例:\n"
                    "[ここにレスポンス例を記入]\n\n"
                    "評価基準:\n"
                    "[ここに評価基準を記入]\n\n"
                    "では、以下の目標に対するレスポンス最適化プロンプトを作成してください:\n\n"
                    "{query}",
                ),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def run(self, query: str) -> str:
        return self.chain.invoke({"query": query})


def main():
    import argparse

    from settings import Settings

    settings = Settings()

    parser = argparse.ArgumentParser(
        description="ResponseOptimizerを利用して、与えられた目標に対して最適化されたレスポンスの定義を生成します"
    )
    parser.add_argument("--task", type=str, required=True, help="実行するタスク")
    args = parser.parse_args()

    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )

    passive_goal_creator = PassiveGoalCreator(llm=llm)
    goal: Goal = passive_goal_creator.run(args.task)

    prompt_optimizer = PromptOptimizer(llm=llm)
    optimized_goal: OptimizedGoal = prompt_optimizer.run(goal=goal)
    response_optimizer = ResponseOptimizer(llm=llm)
    optimized_response: str = response_optimizer.run(query=optimized_goal.text)

    print(f"最適化されたレスポンス定義: {optimized_response}")


if __name__ == "__main__":
    main()
