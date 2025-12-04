# 공통 모듈에서 ReflectionManager와 TaskReflector 클래스 임포트
# ReflectionManager: 리플렉션 데이터를 저장하고 관리하는 클래스
# TaskReflector: 태스크 수행 후 리플렉션(성찰)을 수행하는 클래스
from common.reflection_manager import ReflectionManager, TaskReflector
# Anthropic의 Claude 모델을 사용하기 위한 LangChain 래퍼 클래스 임포트
from langchain_anthropic import ChatAnthropic
# OpenAI의 ChatGPT 모델을 사용하기 위한 LangChain 래퍼 클래스 임포트
from langchain_openai import ChatOpenAI
# self_reflection 모듈에서 ReflectiveAgent 클래스 임포트
# ReflectiveAgent: 자기 성찰 기능을 가진 에이전트
from self_reflection.main import ReflectiveAgent
# logging 모듈: 프로그램 실행 흐름을 추적하기 위한 로깅 기능
import logging

# 로거 설정: 이 모듈의 로거 인스턴스 생성
logger = logging.getLogger(__name__)


# main 함수: Cross-reflection 패턴을 구현하는 진입점
# Cross-reflection: 서로 다른 LLM이 상호 성찰을 통해 품질을 향상시키는 패턴
def main():
    # argparse 모듈: 커맨드 라인 인자를 파싱하기 위해 임포트
    import argparse

    # settings 모듈에서 Settings 클래스 임포트 (프로젝트 설정 관리)
    from settings import Settings

    # Settings 인스턴스 생성: 환경변수나 설정 파일에서 설정값을 로드
    settings = Settings()

    # 로깅 설정: INFO 레벨 이상의 로그를 콘솔에 출력
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',  # 메시지만 출력 (시간, 레벨 등 제외)
        handlers=[logging.StreamHandler()]
    )

    # ArgumentParser 생성: 커맨드 라인 인자를 처리하기 위한 파서 객체
    parser = argparse.ArgumentParser(
        # Cross-reflection 방식으로 태스크를 실행한다는 설명
        description="ReflectiveAgent를 사용해 태스크를 실행합니다(Cross-reflection)"
    )
    # --task 인자 추가: 실행할 태스크를 문자열로 입력받음 (필수)
    parser.add_argument("--task", type=str, required=True, help="실행할 태스크")
    # 커맨드 라인 인자를 파싱하여 args 객체에 저장
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🔄 Cross-Reflection Agent 초기화")
    logger.info("=" * 80)

    # OpenAI LLM 초기화: 주 작업을 수행하는 에이전트용 모델
    # settings에서 모델명과 temperature를 가져와 설정
    openai_llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    logger.info(f"✅ OpenAI LLM 초기화 완료 (모델: {settings.openai_smart_model})")

    # Anthropic LLM 초기화: 리플렉션(성찰)을 수행하는 모델
    # Cross-reflection의 핵심: 다른 제공자의 LLM을 사용하여 교차 검증
    anthropic_llm = ChatAnthropic(
        model=settings.anthropic_smart_model, temperature=settings.temperature
    )
    logger.info(f"✅ Anthropic LLM 초기화 완료 (모델: {settings.anthropic_smart_model})")
    logger.info("📝 Cross-Reflection 설정: OpenAI가 실행, Anthropic이 성찰 수행\n")

    # ReflectionManager 초기화: 리플렉션 데이터를 파일에 저장하고 관리
    # file_path: 리플렉션 데이터를 저장할 JSON 파일 경로
    reflection_manager = ReflectionManager(file_path="tmp/cross_reflection_db.json")

    # Anthropic LLM을 사용하는 TaskReflector 초기화
    # TaskReflector: 태스크 수행 결과를 분석하고 개선점을 도출하는 역할
    # Anthropic 모델을 사용함으로써 OpenAI 모델과 다른 관점에서 성찰 가능
    anthropic_task_reflector = TaskReflector(
        llm=anthropic_llm, reflection_manager=reflection_manager
    )

    # ReflectiveAgent 초기화: 자기 성찰 기능을 가진 에이전트 생성
    # llm: 주 작업을 수행하는 OpenAI 모델
    # reflection_manager: 리플렉션 데이터 관리자
    # task_reflector: Anthropic 모델 기반 리플렉터 (교차 성찰)
    agent = ReflectiveAgent(
        llm=openai_llm,
        reflection_manager=reflection_manager,
        task_reflector=anthropic_task_reflector,
    )

    # 태스크를 실행하고 결과 획득
    # run 메서드: 태스크 수행 → 리플렉션 → 결과 반환의 전체 프로세스 실행
    result = agent.run(args.task)

    # 결과 출력: 최종 실행 결과를 콘솔에 출력
    logger.info("\n" + "=" * 80)
    logger.info("📄 최종 결과")
    logger.info("=" * 80)
    print(result)


# 스크립트가 직접 실행될 때만 main() 함수를 호출
# 모듈로 임포트될 때는 main()이 자동으로 실행되지 않음
if __name__ == "__main__":
    main()
