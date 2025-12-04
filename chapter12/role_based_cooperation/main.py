# operator 모듈: 연산자 함수를 제공 (여기서는 add를 Annotated 타입에 사용)
import operator
# typing 모듈: 타입 힌트를 위한 Annotated(메타데이터 포함 타입), Any(모든 타입) 임포트
from typing import Annotated, Any
# logging 모듈: 프로그램 실행 흐름을 추적하기 위한 로깅 기능
import logging

# LangChain 커뮤니티 도구: Tavily 검색 엔진을 사용한 웹 검색 도구
from langchain_community.tools.tavily_search import TavilySearchResults
# LangChain 메시지 타입: HumanMessage(사용자 메시지), SystemMessage(시스템 메시지)
from langchain_core.messages import HumanMessage, SystemMessage
# LangChain 출력 파서: LLM 출력을 문자열로 변환하는 파서
from langchain_core.output_parsers import StrOutputParser
# LangChain 프롬프트 템플릿: 대화형 프롬프트를 생성하기 위한 템플릿 클래스
from langchain_core.prompts import ChatPromptTemplate
# OpenAI의 ChatGPT 모델을 사용하기 위한 LangChain 래퍼 클래스
from langchain_openai import ChatOpenAI
# LangGraph: 상태 기반 그래프 워크플로우를 구성하기 위한 클래스들
from langgraph.graph import END, StateGraph
# LangGraph 미리 빌드된 에이전트: ReAct 패턴 에이전트 생성 함수
from langgraph.prebuilt import create_react_agent
# Pydantic: 데이터 검증 및 구조화를 위한 BaseModel과 Field 임포트
from pydantic import BaseModel, Field
# single_path_plan_generation 모듈: DecomposedTasks 모델과 QueryDecomposer 클래스 임포트
from single_path_plan_generation.main import DecomposedTasks, QueryDecomposer

# 로거 설정: 이 모듈의 로거 인스턴스 생성
logger = logging.getLogger(__name__)


# Role 클래스: 태스크를 수행할 역할(페르소나)을 정의하는 모델
# Role-based cooperation의 핵심: 각 태스크에 특화된 역할을 배정
class Role(BaseModel):
    # name 필드: 역할의 이름 (예: "데이터 분석 전문가", "시장 조사원" 등)
    name: str = Field(..., description="역할의 이름")
    # description 필드: 이 역할이 무엇을 하는지에 대한 상세 설명
    description: str = Field(..., description="역할에 대한 상세 설명")
    # key_skills 필드: 이 역할이 가진 주요 스킬이나 속성 리스트 (3가지)
    key_skills: list[str] = Field(..., description="이 역할에 필요한 주요 스킬이나 속성")


# Task 클래스: 실행할 태스크와 그 태스크에 배정된 역할을 포함하는 모델
class Task(BaseModel):
    # description 필드: 태스크에 대한 설명
    description: str = Field(..., description="태스크 설명")
    # role 필드: 이 태스크를 수행할 역할 (Role 객체)
    role: Role = Field(default=None, description="태스크에 배정된 역할")


# TasksWithRoles 클래스: 역할이 배정된 태스크들의 컨테이너
# LLM이 태스크 리스트와 각각에 대한 역할을 함께 생성하도록 구조화
class TasksWithRoles(BaseModel):
    # tasks 필드: 역할이 배정된 Task 객체들의 리스트
    tasks: list[Task] = Field(..., description="역할이 배정된 태스크 목록")


# AgentState 클래스: Role-based cooperation 워크플로우의 상태를 관리하는 모델
class AgentState(BaseModel):
    # query 필드: 사용자가 최초에 입력한 쿼리
    query: str = Field(..., description="사용자가 입력한 쿼리")
    # tasks 필드: 역할이 배정된 실행할 태스크 목록
    tasks: list[Task] = Field(
        default_factory=list, description="실행할 태스크 목록"
    )
    # current_task_index 필드: 현재 실행 중인 태스크의 인덱스
    current_task_index: int = Field(default=0, description="현재 실행 중인 태스크의 번호")
    # results 필드: 각 태스크 실행 결과를 순차적으로 저장하는 리스트
    # Annotated[list[str], operator.add]: 새로운 결과가 기존 리스트에 추가됨
    results: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="실행 완료된 태스크의 결과 목록"
    )
    # final_report 필드: 모든 태스크 완료 후 생성된 최종 보고서
    final_report: str = Field(default="", description="최종 출력 결과")


class Planner:
    def __init__(self, llm: ChatOpenAI):
        self.query_decomposer = QueryDecomposer(llm=llm)

    def run(self, query: str) -> list[Task]:
        logger.info("📋 [계획 수립] 목표를 태스크로 분해 중...")
        decomposed_tasks: DecomposedTasks = self.query_decomposer.run(query=query)
        tasks = [Task(description=task) for task in decomposed_tasks.values]
        logger.info(f"  총 {len(tasks)}개의 태스크 생성 완료\n")
        return tasks


class RoleAssigner:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm.with_structured_output(TasksWithRoles)

    def run(self, tasks: list[Task]) -> list[Task]:
        logger.info("👥 [역할 배정] 각 태스크에 적합한 역할 배정 중...")
        prompt = ChatPromptTemplate(
            [
                (
                    "system",
                    (
                        "당신은 창의적인 역할 설계 전문가입니다. 주어진 태스크에 대해 독특하고 적절한 역할을 생성하세요."
                    ),
                ),
                (
                    "human",
                    (
                        "태스크:\n{tasks}\n\n"
                        "이러한 태스크에 대해 다음 지침에 따라 역할을 배정하세요:\n"
                        "1. 각 태스크에 대해 독창적이고 창의적인 역할을 고안하세요. 기존 직업명이나 일반적인 역할명에 얽매일 필요는 없습니다.\n"
                        "2. 역할명은 해당 태스크의 본질을 반영한 매력적이고 기억에 남는 것으로 지어주세요.\n"
                        "3. 각 역할에 대해, 그 역할이 해당 태스크에 왜 최적인지 상세히 설명하세요.\n"
                        "4. 그 역할이 효과적으로 태스크를 수행하기 위해 필요한 주요 스킬이나 속성을 3가지 들어주세요.\n\n"
                        "창의성을 발휘하여 태스크의 본질을 포착한 혁신적인 역할을 생성하세요."
                    ),
                ),
            ],
        )
        chain = prompt | self.llm
        tasks_with_roles = chain.invoke(
            {"tasks": "\n".join([task.description for task in tasks])}
        )
        logger.info(f"  역할 배정 완료:")
        for i, task in enumerate(tasks_with_roles.tasks, 1):
            logger.info(f"    태스크 {i}: {task.role.name}")
        logger.info("")
        return tasks_with_roles.tasks


class Executor:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.tools = [TavilySearchResults(max_results=3)]
        self.base_agent = create_react_agent(self.llm, self.tools)

    def run(self, task: Task) -> str:
        logger.info(f"⚙️  [태스크 실행] 역할: {task.role.name}")
        logger.info(f"  태스크: {task.description[:80]}...")
        result = self.base_agent.invoke(
            {
                "messages": [
                    (
                        "system",
                        (
                            f"당신은 {task.role.name}입니다.\n"
                            f"설명: {task.role.description}\n"
                            f"주요 스킬: {', '.join(task.role.key_skills)}\n"
                            "당신의 역할에 기반하여 주어진 태스크를 최고의 능력으로 수행해 주세요."
                        ),
                    ),
                    (
                        "human",
                        f"다음 태스크를 실행해 주세요:\n\n{task.description}",
                    ),
                ]
            }
        )
        content = result["messages"][-1].content
        logger.info(f"  ✓ 실행 완료 (결과 길이: {len(content)} 글자)\n")
        return content


class Reporter:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(self, query: str, results: list[str]) -> str:
        logger.info("📊 [보고서 생성] 모든 결과를 종합하여 최종 보고서 작성 중...")
        logger.info(f"  수집된 결과 개수: {len(results)}개")
        prompt = ChatPromptTemplate(
            [
                (
                    "system",
                    (
                        "당신은 종합적인 보고서 작성 전문가입니다. 여러 정보원의 결과를 통합하고, 통찰력 있는 포괄적인 보고서를 작성하는 능력이 있습니다."
                    ),
                ),
                (
                    "human",
                    (
                        "태스크: 다음 정보를 바탕으로 포괄적이고 일관성 있는 답변을 작성하세요.\n"
                        "요구사항:\n"
                        "1. 제공된 모든 정보를 통합하여 잘 구성된 답변을 만들어주세요.\n"
                        "2. 답변은 원래 쿼리에 직접 응답하는 형태로 작성하세요.\n"
                        "3. 각 정보의 중요 포인트나 발견 사항을 포함하세요.\n"
                        "4. 마지막에 결론이나 요약을 제공하세요.\n"
                        "5. 답변은 상세하면서도 간결하게 작성하고, 250~300단어 정도를 목표로 하세요.\n"
                        "6. 답변은 한국어로 작성하세요.\n\n"
                        "사용자 요청: {query}\n\n"
                        "수집한 정보:\n{results}"
                    ),
                ),
            ],
        )
        chain = prompt | self.llm | StrOutputParser()
        report = chain.invoke(
            {
                "query": query,
                "results": "\n\n".join(
                    f"Info {i+1}:\n{result}" for i, result in enumerate(results)
                ),
            }
        )
        logger.info(f"  보고서 생성 완료 (길이: {len(report)} 글자)\n")
        return report


class RoleBasedCooperation:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.planner = Planner(llm=llm)
        self.role_assigner = RoleAssigner(llm=llm)
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
        workflow.add_edge("role_assigner", "executor")
        workflow.add_conditional_edges(
            "executor",
            lambda state: state.current_task_index < len(state.tasks),
            {True: "executor", False: "reporter"},
        )

        workflow.add_edge("reporter", END)

        return workflow.compile()

    def _plan_tasks(self, state: AgentState) -> dict[str, Any]:
        logger.info("=" * 80)
        logger.info("📋 [1단계: 계획 수립] 시작")
        logger.info("=" * 80)
        tasks = self.planner.run(query=state.query)
        logger.info("✅ [1단계: 계획 수립] 완료\n")
        return {"tasks": tasks}

    def _assign_roles(self, state: AgentState) -> dict[str, Any]:
        logger.info("=" * 80)
        logger.info("👥 [2단계: 역할 배정] 시작")
        logger.info("=" * 80)
        tasks_with_roles = self.role_assigner.run(tasks=state.tasks)
        logger.info("✅ [2단계: 역할 배정] 완료\n")
        return {"tasks": tasks_with_roles}

    def _execute_task(self, state: AgentState) -> dict[str, Any]:
        current_task_num = state.current_task_index + 1
        total_tasks = len(state.tasks)

        if state.current_task_index == 0:
            logger.info("=" * 80)
            logger.info("⚙️  [3단계: 태스크 실행] 시작")
            logger.info("=" * 80)

        logger.info(f"📝 태스크 {current_task_num}/{total_tasks} 실행 중")
        current_task = state.tasks[state.current_task_index]
        result = self.executor.run(task=current_task)

        if state.current_task_index == len(state.tasks) - 1:
            logger.info("✅ [3단계: 태스크 실행] 모든 태스크 완료\n")

        return {
            "results": [result],
            "current_task_index": state.current_task_index + 1,
        }

    def _generate_report(self, state: AgentState) -> dict[str, Any]:
        logger.info("=" * 80)
        logger.info("📊 [4단계: 보고서 생성] 시작")
        logger.info("=" * 80)
        report = self.reporter.run(query=state.query, results=state.results)
        logger.info("✅ [4단계: 보고서 생성] 완료\n")
        return {"final_report": report}

    def run(self, query: str) -> str:
        logger.info("=" * 80)
        logger.info("🎬 Role-Based Cooperation Agent 시작")
        logger.info("=" * 80)
        logger.info(f"사용자 쿼리: {query}\n")
        initial_state = AgentState(query=query)
        final_state = self.graph.invoke(initial_state, {"recursion_limit": 1000})
        logger.info("=" * 80)
        logger.info("🎉 Role-Based Cooperation Agent 완료")
        logger.info("=" * 80)
        return final_state["final_report"]


# main 함수: Role-based cooperation 패턴으로 태스크를 실행하는 진입점
# 프로세스: 1) 계획 수립 → 2) 역할 배정 → 3) 각 역할로 태스크 실행 → 4) 결과 종합
def main():
    # argparse 모듈: 커맨드 라인 인자를 파싱하기 위해 임포트
    import argparse

    # settings 모듈에서 Settings 클래스 임포트
    from settings import Settings

    # Settings 인스턴스 생성
    settings = Settings()

    # 로깅 설정: INFO 레벨 이상의 로그를 콘솔에 출력
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',  # 메시지만 출력 (시간, 레벨 등 제외)
        handlers=[logging.StreamHandler()]
    )

    # ArgumentParser 생성
    parser = argparse.ArgumentParser(
        # Role-based cooperation 방식으로 태스크 실행
        description="RoleBasedCooperation을 사용하여 태스크를 실행합니다"
    )
    # --task 인자 추가
    parser.add_argument("--task", type=str, required=True, help="실행할 태스크")
    # 커맨드 라인 인자 파싱
    args = parser.parse_args()

    # ChatOpenAI 인스턴스 생성
    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    # RoleBasedCooperation 에이전트 생성
    agent = RoleBasedCooperation(llm=llm)
    # 태스크 실행: 각 태스크에 적절한 역할을 배정하고 실행
    result = agent.run(query=args.task)
    # 최종 결과 출력
    logger.info("\n" + "=" * 80)
    logger.info("📄 최종 결과")
    logger.info("=" * 80)
    print(result)


# 스크립트가 직접 실행될 때만 main() 함수를 호출
if __name__ == "__main__":
    main()
