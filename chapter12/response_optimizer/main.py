# LangChain 출력 파서: LLM 출력을 문자열로 변환하는 파서
from langchain_core.output_parsers import StrOutputParser
# LangChain 프롬프트 템플릿: 대화형 프롬프트를 생성하기 위한 템플릿 클래스
from langchain_core.prompts import ChatPromptTemplate
# OpenAI의 ChatGPT 모델을 사용하기 위한 LangChain 래퍼 클래스
from langchain_openai import ChatOpenAI
# passive_goal_creator 모듈에서 Goal과 PassiveGoalCreator 임포트
from passive_goal_creator.main import Goal, PassiveGoalCreator
# prompt_optimizer 모듈에서 OptimizedGoal과 PromptOptimizer 임포트
from prompt_optimizer.main import OptimizedGoal, PromptOptimizer


# ResponseOptimizer 클래스: 목표에 맞는 최적의 응답 형식을 정의하는 클래스
# 목표가 정해진 후, 어떤 형식으로 응답을 생성해야 하는지 사양을 수립
class ResponseOptimizer:
    # 생성자: LLM 인스턴스를 받아 초기화
    def __init__(self, llm: ChatOpenAI):
        # LLM 인스턴스를 저장하여 응답 최적화에 사용
        self.llm = llm

    # run 메서드: 목표를 받아 최적화된 응답 사양을 문자열로 반환
    def run(self, query: str) -> str:
        # ChatPromptTemplate.from_messages: 시스템 메시지와 사용자 메시지로 구성된 프롬프트 생성
        # from_messages는 여러 역할(system, human 등)의 메시지를 조합할 수 있음
        prompt = ChatPromptTemplate.from_messages(
            [
                # 시스템 메시지: LLM의 역할과 임무를 정의
                (
                    "system",
                    # LLM을 "응답 최적화 전문가"로 설정하여 응답 사양 수립에 집중하도록 함
                    "당신은 AI 에이전트 시스템의 응답 최적화 전문가입니다. 주어진 목표에 대해 에이전트가 목표에 맞는 응답을 반환하기 위한 응답 사양을 수립해 주세요.",
                ),
                # 사용자 메시지: 구체적인 작업 지시사항과 절차
                (
                    "human",
                    # 5단계 절차로 응답 최적화 프롬프트 작성 요청
                    "다음 절차에 따라 응답 최적화 프롬프트를 작성해 주세요:\n\n"
                    # 절차 1: 목표 분석 - 목표의 주요 요소와 의도 파악
                    "1. 목표 분석:\n"
                    "제시된 목표를 분석하고 주요 요소와 의도를 파악해 주세요.\n\n"
                    # 절차 2: 응답 사양 수립 - 톤, 구조, 내용 초점 결정
                    "2. 응답 사양 수립:\n"
                    "목표 달성을 위한 최적의 응답 사양을 고안해 주세요. 톤, 구조, 내용의 초점 등을 고려해 주세요.\n\n"
                    # 절차 3: 구체적인 지침 작성 - AI 에이전트가 따라야 할 명확한 지침
                    # 중요: AI 에이전트는 이미 조사된 결과만 정리 가능, 인터넷 접근 불가
                    "3. 구체적인 지침 작성:\n"
                    "사전에 수집된 정보에서 사용자의 기대에 부합하는 응답을 위해 필요한, AI 에이전트에 대한 명확하고 실행 가능한 지침을 작성해 주세요. 귀하의 지침으로 AI 에이전트가 수행할 수 있는 것은 이미 조사된 결과를 정리하는 것뿐입니다. 인터넷에 접근할 수 없습니다.\n\n"
                    # 절차 4: 예시 제공 - 목표에 맞는 응답의 구체적 예시
                    "4. 예시 제공:\n"
                    "가능하다면, 목표에 맞는 응답의 예시를 하나 이상 포함해 주세요.\n\n"
                    # 절차 5: 평가 기준 설정 - 응답 효과 측정 기준 정의
                    "5. 평가 기준 설정:\n"
                    "응답의 효과를 측정하기 위한 기준을 정의해 주세요.\n\n"
                    # 출력 구조 정의: 5개 섹션으로 구성된 형식 지정
                    "다음 구조로 응답 최적화 프롬프트를 출력해 주세요:\n\n"
                    "목표 분석:\n"
                    "[여기에 목표 분석 결과를 기입]\n\n"
                    "응답 사양:\n"
                    "[여기에 수립된 응답 사양을 기입]\n\n"
                    "AI 에이전트에 대한 지침:\n"
                    "[여기에 AI 에이전트에 대한 구체적인 지침을 기입]\n\n"
                    "응답 예시:\n"
                    "[여기에 응답 예시를 기입]\n\n"
                    "평가 기준:\n"
                    "[여기에 평가 기준을 기입]\n\n"
                    # {query} 플레이스홀더: 목표가 동적으로 삽입될 위치
                    "그럼, 다음 목표에 대한 응답 최적화 프롬프트를 작성해 주세요:\n"
                    "{query}",
                ),
            ]
        )
        # chain 생성: 프롬프트 → LLM → 문자열 파서 순서로 연결
        # StrOutputParser()는 LLM의 출력을 문자열로 변환
        chain = prompt | self.llm | StrOutputParser()
        # chain.invoke: 프롬프트에 query를 전달하여 LLM 호출 및 응답 사양 반환
        return chain.invoke({"query": query})


# main 함수: 스크립트가 직접 실행될 때 호출되는 진입점
# 3단계 프로세스: 1) 기본 목표 생성 → 2) SMART 원칙으로 최적화 → 3) 응답 사양 수립
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
        description="ResponseOptimizer를 이용하여 주어진 목표에 대해 최적화된 응답 정의를 생성합니다"
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
    optimized_goal: OptimizedGoal = prompt_optimizer.run(query=goal.text)

    # === 3단계: 응답 사양 수립 ===
    # ResponseOptimizer 인스턴스 생성: 최적화된 목표에 맞는 응답 형식 정의
    response_optimizer = ResponseOptimizer(llm=llm)
    # run 메서드 호출: 2단계의 최적화된 목표를 기반으로 응답 사양 생성
    # 응답 사양: 톤, 구조, 내용 초점, 지침, 예시, 평가 기준 등을 포함
    optimized_response: str = response_optimizer.run(query=optimized_goal.text)

    # 생성된 응답 사양을 출력
    print(f"{optimized_response}")


# 스크립트가 직접 실행될 때만 main() 함수를 호출
# 모듈로 임포트될 때는 main()이 자동으로 실행되지 않음
if __name__ == "__main__":
    main()
