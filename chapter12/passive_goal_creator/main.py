# LangChain의 프롬프트 템플릿을 생성하기 위한 클래스 임포트
from langchain_core.prompts import ChatPromptTemplate
# OpenAI의 ChatGPT 모델을 사용하기 위한 LangChain 래퍼 클래스 임포트
from langchain_openai import ChatOpenAI
# 데이터 검증 및 구조화를 위한 Pydantic의 기본 클래스 및 필드 정의 도구 임포트
from pydantic import BaseModel, Field


# Goal 클래스: LLM이 생성한 목표를 구조화된 형태로 저장하는 데이터 모델
class Goal(BaseModel):
    # description 필드: 목표에 대한 설명을 저장하는 문자열 필드
    # Field(...)는 필수 필드를 의미하며, description 파라미터는 LLM에게 이 필드의 용도를 설명
    description: str = Field(..., description="목표 설명")

    # text 프로퍼티: Goal 객체를 텍스트 형태로 반환하는 읽기 전용 속성
    # @property 데코레이터를 사용하여 메서드를 속성처럼 접근 가능하게 함
    @property
    def text(self) -> str:
        # description 필드의 값을 포맷팅하여 문자열로 반환
        return f"{self.description}"


# PassiveGoalCreator 클래스: 사용자 입력을 분석하여 실행 가능한 목표를 생성하는 클래스
# "Passive"는 LLM이 직접 행동하지 않고 조사 및 보고서 생성에만 집중함을 의미
class PassiveGoalCreator:
    # 생성자: PassiveGoalCreator 인스턴스를 초기화
    def __init__(
        self,
        llm: ChatOpenAI,  # OpenAI 챗 모델 인스턴스를 인자로 받음
    ):
        # 전달받은 LLM 인스턴스를 인스턴스 변수로 저장하여 클래스 내에서 사용
        self.llm = llm

    # run 메서드: 사용자 쿼리를 받아 목표를 생성하고 반환하는 핵심 메서드
    def run(self, query: str) -> Goal:
        # ChatPromptTemplate.from_template: 문자열 템플릿으로부터 프롬프트 객체 생성
        # 이 프롬프트는 LLM에게 사용자 입력을 분석하여 목표를 생성하도록 지시
        prompt = ChatPromptTemplate.from_template(
            # 프롬프트의 주요 지시사항: 명확하고 실행 가능한 목표 생성 요청
            "사용자 입력을 분석하여 명확하고 실행 가능한 목표를 생성해 주세요.\n"
            "요건:\n"
            # 요건 1: 목표의 구체성과 명확성을 강조
            "1. 목표는 구체적이고 명확해야 하며, 실행 가능한 수준으로 상세화되어야 합니다.\n"
            # 요건 2: LLM이 수행할 수 있는 행동의 범위를 명확히 제한
            "2. 당신이 실행할 수 있는 행동은 다음과 같은 행동뿐입니다.\n"
            "   - 인터넷을 이용하여 목표 달성을 위한 조사를 수행합니다.\n"
            "   - 사용자를 위한 보고서를 생성합니다.\n"
            # 요건 3: 행동 범위를 벗어나는 것을 명시적으로 금지
            "3. 절대 2.에 명시된 행동 외의 다른 행동을 취해서는 안 됩니다.\n"
            # {query} 플레이스홀더: 사용자 입력이 동적으로 삽입될 위치
            "사용자 입력: {query}"
        )
        # chain 생성: 프롬프트와 LLM을 파이프(|) 연산자로 연결
        # with_structured_output(Goal): LLM의 출력을 Goal 클래스 형태로 구조화
        chain = prompt | self.llm.with_structured_output(Goal)
        # chain.invoke: 실제로 LLM을 호출하여 결과를 받아옴
        # {"query": query}는 프롬프트 템플릿의 {query} 플레이스홀더에 전달될 값
        return chain.invoke({"query": query})


# main 함수: 스크립트가 직접 실행될 때 호출되는 진입점
def main():
    # argparse 모듈: 커맨드 라인 인자를 파싱하기 위해 임포트
    import argparse

    # settings 모듈에서 Settings 클래스 임포트 (프로젝트 설정 관리)
    from settings import Settings

    # Settings 인스턴스 생성: 환경변수나 설정 파일에서 설정값을 로드
    settings = Settings()

    # ArgumentParser 생성: 커맨드 라인 인자를 처리하기 위한 파서 객체
    parser = argparse.ArgumentParser(
        # 스크립트 실행 시 도움말에 표시될 설명
        description="PassiveGoalCreator를 사용하여 목표를 생성합니다"
    )
    # --task 인자 추가: 실행할 태스크를 문자열로 받음 (필수 인자)
    parser.add_argument("--task", type=str, required=True, help="실행할 태스크")
    # 커맨드 라인 인자를 파싱하여 args 객체에 저장
    args = parser.parse_args()

    # ChatOpenAI 인스턴스 생성: OpenAI의 챗 모델을 초기화
    # model: settings에서 가져온 스마트 모델명 사용 (예: gpt-4)
    # temperature: 응답의 창의성/무작위성을 조절하는 파라미터 (0~1)
    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    # PassiveGoalCreator 인스턴스 생성: 초기화된 LLM을 전달
    goal_creator = PassiveGoalCreator(llm=llm)
    # run 메서드 호출: 사용자가 입력한 태스크를 기반으로 목표 생성
    # result는 Goal 타입의 객체
    result: Goal = goal_creator.run(query=args.task)

    # 생성된 목표의 텍스트 표현을 출력
    print(f"{result.text}")


# 스크립트가 직접 실행될 때만 main() 함수를 호출
# 모듈로 임포트될 때는 main()이 자동으로 실행되지 않음
if __name__ == "__main__":
    main()
