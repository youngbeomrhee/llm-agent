# LangChain의 프롬프트 템플릿을 생성하기 위한 클래스 임포트
from langchain_core.prompts import ChatPromptTemplate
# OpenAI의 ChatGPT 모델을 사용하기 위한 LangChain 래퍼 클래스 임포트
from langchain_openai import ChatOpenAI
# passive_goal_creator 모듈에서 Goal 클래스와 PassiveGoalCreator 클래스 임포트
# Goal: 기본 목표 데이터 모델, PassiveGoalCreator: 초기 목표 생성 클래스
from passive_goal_creator.main import Goal, PassiveGoalCreator
# 데이터 검증 및 구조화를 위한 Pydantic의 기본 클래스 및 필드 정의 도구 임포트
from pydantic import BaseModel, Field


# OptimizedGoal 클래스: SMART 원칙에 따라 최적화된 목표를 저장하는 데이터 모델
# Goal 클래스와 달리 측정 기준(metrics) 필드가 추가됨
class OptimizedGoal(BaseModel):
    # description 필드: 최적화된 목표의 설명을 저장하는 문자열 필드
    # Field(...)는 필수 필드를 의미
    description: str = Field(..., description="목표의 설명")
    # metrics 필드: 목표 달성도를 측정하는 방법을 저장하는 문자열 필드
    # SMART 원칙 중 'Measurable(측정 가능)'을 구현하기 위한 필드
    metrics: str = Field(..., description="목표의 달성도를 측정하는 방법")

    # text 프로퍼티: OptimizedGoal 객체를 사람이 읽기 쉬운 텍스트로 반환
    # @property 데코레이터로 메서드를 속성처럼 접근 가능하게 함
    @property
    def text(self) -> str:
        # 목표 설명과 측정 기준을 함께 표시하는 포맷팅된 문자열 반환
        return f"{self.description}(측정 기준: {self.metrics})"


# PromptOptimizer 클래스: 기본 목표를 SMART 원칙에 따라 최적화하는 클래스
# 입력받은 목표를 분석하여 더 구체적이고 측정 가능한 형태로 재구성
class PromptOptimizer:
    # 생성자: PromptOptimizer 인스턴스를 초기화
    def __init__(self, llm: ChatOpenAI):
        # 전달받은 LLM 인스턴스를 인스턴스 변수로 저장
        self.llm = llm

    # run 메서드: 입력된 목표를 최적화하여 OptimizedGoal 객체로 반환
    def run(self, query: str) -> OptimizedGoal:
        # ChatPromptTemplate.from_template: 목표 최적화를 위한 프롬프트 템플릿 생성
        # 문자열 연결(\n)을 사용하여 여러 줄 프롬프트 구성
        prompt = ChatPromptTemplate.from_template(
            # 역할 설정: LLM을 목표 설정 전문가로 설정하고 SMART 원칙 소개
            # SMART: Specific(구체적), Measurable(측정가능), Achievable(달성가능),
            #        Relevant(관련성), Time-bound(기한)
            "당신은 목표 설정 전문가입니다. 아래의 목표를 SMART 원칙(Specific: 구체적, Measurable: 측정 가능, Achievable: 달성 가능, Relevant: 관련성이 높은, Time-bound: 기한이 있는)에 기반하여 최적화해 주세요.\n\n"
            # 원래 목표 섹션 헤더
            "원래 목표:\n"
            # {query} 플레이스홀더: 최적화할 원본 목표가 동적으로 삽입될 위치
            "{query}\n\n"
            # 지시 사항 섹션 헤더
            "지시 사항:\n"
            # 지시 1: 원본 목표 분석 및 개선점 파악 요청
            "1. 원래 목표를 분석하고, 부족한 요소나 개선점을 파악해 주세요.\n"
            # 지시 2: 수행 가능한 행동 범위를 명확히 제한
            "2. 당신이 실행할 수 있는 행동은 다음과 같습니다.\n"
            "   - 인터넷을 이용하여 목표 달성을 위한 조사를 수행한다.\n"
            "   - 사용자를 위한 보고서를 생성한다.\n"
            # 지시 3: SMART 원칙 적용 및 구체화 요청
            "3. SMART 원칙의 각 요소를 고려하면서 목표를 구체적이고 상세하게 기술해 주세요.\n"
            # 지시 3-1: 추상적 표현 금지 (구체성 강화)
            "   - 절대 추상적인 표현을 포함해서는 안 됩니다.\n"
            # 지시 3-2: 모든 표현이 실행 가능하고 구체적인지 확인 요청
            "   - 반드시 모든 단어가 실행 가능하고 구체적인지 확인해 주세요.\n"
            # 지시 4: 측정 가능성(Measurable) 구현을 위한 측정 방법 기술 요청
            "4. 목표의 달성도를 측정하는 방법을 구체적이고 상세하게 기술해 주세요.\n"
            # 지시 5: Time-bound 요소에 대한 유연성 부여 (기한이 없으면 추가하지 않음)
            "5. 원래 목표에서 기한이 지정되지 않은 경우에는 기한을 고려할 필요가 없습니다.\n"
            # 지시 6: 행동 범위 제한 재강조 (안전장치)
            "6. 주의: 절대로 2번 이외의 행동을 취해서는 안 됩니다."
        )
        # chain 생성: 프롬프트와 LLM을 파이프 연산자로 연결
        # with_structured_output(OptimizedGoal): LLM 출력을 OptimizedGoal 형태로 구조화
        chain = prompt | self.llm.with_structured_output(OptimizedGoal)
        # chain.invoke: 프롬프트에 query를 전달하여 LLM 호출 및 최적화된 목표 반환
        return chain.invoke({"query": query})


# main 함수: 스크립트가 직접 실행될 때 호출되는 진입점
# 2단계 프로세스: 1) 기본 목표 생성 → 2) SMART 원칙으로 최적화
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
        description="PromptOptimizer를 이용하여 생성된 목표 리스트를 최적화합니다"
    )
    # --task 인자 추가: 사용자가 원하는 태스크를 문자열로 입력받음 (필수)
    parser.add_argument("--task", type=str, required=True, help="실행할 태스크")
    # 커맨드 라인 인자를 파싱하여 args 객체에 저장
    args = parser.parse_args()

    # ChatOpenAI 인스턴스 생성: OpenAI의 챗 모델 초기화
    # settings에서 모델명과 temperature 값을 가져와 설정
    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )

    # === 1단계: 기본 목표 생성 ===
    # PassiveGoalCreator 인스턴스 생성: 사용자 입력으로부터 기본 목표 생성
    passive_goal_creator = PassiveGoalCreator(llm=llm)
    # run 메서드 호출: 사용자 태스크를 기반으로 기본 목표(Goal) 생성
    goal: Goal = passive_goal_creator.run(query=args.task)

    # === 2단계: 목표 최적화 ===
    # PromptOptimizer 인스턴스 생성: 기본 목표를 SMART 원칙으로 최적화
    prompt_optimizer = PromptOptimizer(llm=llm)
    # run 메서드 호출: 1단계에서 생성된 목표를 최적화하여 OptimizedGoal 생성
    # goal.text를 사용하여 Goal 객체의 텍스트 표현을 전달
    optimised_goal: OptimizedGoal = prompt_optimizer.run(query=goal.text)

    # 최적화된 목표의 텍스트 표현(설명 + 측정 기준)을 출력
    print(f"{optimised_goal.text}")


# 스크립트가 직접 실행될 때만 main() 함수를 호출
# 모듈로 임포트될 때는 main()이 자동으로 실행되지 않음
if __name__ == "__main__":
    main()
