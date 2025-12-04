# operator 모듈: 연산자 함수를 제공 (여기서는 add를 Annotated 타입에 사용)
import operator
# datetime 모듈: 현재 날짜/시간 정보를 가져오기 위해 사용
from datetime import datetime
# typing 모듈: 타입 힌트를 위한 Annotated(메타데이터 포함 타입), Any(모든 타입) 임포트
from typing import Annotated, Any
# logging 모듈: 프로그램 실행 흐름을 추적하기 위한 로깅 기능
import logging

# LangChain 커뮤니티 도구: Tavily 검색 엔진을 사용한 웹 검색 도구
from langchain_community.tools.tavily_search import TavilySearchResults
# LangChain 출력 파서: LLM 출력을 문자열로 변환하는 파서
from langchain_core.output_parsers import StrOutputParser
# LangChain 프롬프트 템플릿: 대화형 프롬프트를 생성하기 위한 템플릿 클래스
from langchain_core.prompts import ChatPromptTemplate
# OpenAI의 ChatGPT 모델을 사용하기 위한 LangChain 래퍼 클래스
from langchain_openai import ChatOpenAI
# LangGraph: 상태 기반 그래프 워크플로우를 구성하기 위한 클래스들
# END: 그래프의 종료 노드, StateGraph: 상태 기반 워크플로우 그래프
from langgraph.graph import END, StateGraph
# LangGraph 미리 빌드된 에이전트: ReAct 패턴 에이전트 생성 함수
from langgraph.prebuilt import create_react_agent
# passive_goal_creator 모듈: Goal 모델과 PassiveGoalCreator 클래스 임포트
from passive_goal_creator.main import Goal, PassiveGoalCreator
# prompt_optimizer 모듈: OptimizedGoal 모델과 PromptOptimizer 클래스 임포트
from prompt_optimizer.main import OptimizedGoal, PromptOptimizer
# Pydantic: 데이터 검증 및 구조화를 위한 BaseModel과 Field 임포트
from pydantic import BaseModel, Field
# response_optimizer 모듈: ResponseOptimizer 클래스 임포트
from response_optimizer.main import ResponseOptimizer

# 로거 설정: 이 모듈의 로거 인스턴스 생성
logger = logging.getLogger(__name__)


# 로깅 헬퍼 함수: 로거와 print를 동시에 사용하여 notebook에서도 출력이 보이도록 함
def log_and_print(message: str):
    """로거와 print를 동시에 호출하여 콘솔과 notebook 모두에서 출력"""
    logger.info(message)
    # print(message)


# DecomposedTasks 클래스: 분해된 태스크들을 담는 컨테이너
# Single Path에서는 하나의 선형 경로로 실행할 3~5개의 태스크를 저장
class DecomposedTasks(BaseModel):
    # values 필드: 태스크 문자열들의 리스트
    # min_items=3, max_items=5: 3~5개의 태스크로 분해하도록 제약
    values: list[str] = Field(
        default_factory=list,
        min_items=3,
        max_items=10,
        description="3~5개로 분해된 태스크",
    )


# SinglePathPlanGenerationState 클래스: Single Path 워크플로우의 상태 관리
# LangGraph의 StateGraph에서 사용되며, 각 노드 간 데이터 전달을 담당
class SinglePathPlanGenerationState(BaseModel):
    # query 필드: 사용자가 최초에 입력한 쿼리
    query: str = Field(..., description="사용자가 입력한 쿼리")
    # optimized_goal 필드: SMART 원칙으로 최적화된 목표
    optimized_goal: str = Field(default="", description="최적화된 목표")
    # optimized_response 필드: 최종 응답의 형식과 구조에 대한 정의
    optimized_response: str = Field(
        default="", description="최적화된 응답 정의"
    )
    # tasks 필드: 분해된 태스크들의 리스트 (순차적으로 실행됨)
    tasks: list[str] = Field(default_factory=list, description="실행할 태스크 리스트")
    # current_task_index 필드: 현재 실행 중인 태스크의 인덱스
    current_task_index: int = Field(default=0, description="현재 실행 중인 태스크 번호")
    # results 필드: 각 태스크 실행 결과를 순차적으로 저장하는 리스트
    # Annotated[list[str], operator.add]: 새로운 결과가 기존 리스트에 추가됨
    results: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="실행 완료된 태스크 결과 리스트"
    )
    # final_output 필드: 모든 태스크 완료 후 집계된 최종 출력
    final_output: str = Field(default="", description="최종 출력 결과")


# QueryDecomposer 클래스: 목표를 3~7개의 순차적 태스크로 분해하는 클래스
# Single Path의 핵심: 복잡한 목표를 선형적으로 실행 가능한 단계들로 나눔
class QueryDecomposer:
    # 생성자: LLM을 받아 초기화
    def __init__(self, llm: ChatOpenAI):
        # LLM 인스턴스 저장
        self.llm = llm
        # 현재 날짜를 YYYY-MM-DD 형식으로 저장 (프롬프트에 컨텍스트로 제공)
        self.current_date = datetime.now().strftime("%Y-%m-%d")

    # run 메서드: 쿼리를 받아 DecomposedTasks 객체로 분해하여 반환
    def run(self, query: str) -> DecomposedTasks:
        log_and_print("📋 [단계 2] 목표 분해 시작")
        log_and_print(f"  목표: {query[:100]}...")

        prompt = ChatPromptTemplate.from_template(
            f"CURRENT_DATE: {self.current_date}\n"
            "-----\n"
            "태스크: 주어진 목표를 구체적이고 실행 가능한 태스크로 분해해 주세요.\n"
            "요건:\n"
            "1. 다음 행동만으로 목표를 달성할 것. 절대 지정된 이외의 행동을 취하지 말 것.\n"
            "   - 인터넷을 이용하여 목표 달성을 위한 조사를 수행한다.\n"
            "2. 각 태스크는 구체적이고 상세하게 기재하며, 단독으로 실행 및 검증 가능한 정보를 포함할 것. 추상적인 표현을 일절 포함하지 말 것.\n"
            "3. 태스크는 실행 가능한 순서로 리스트화할 것.\n"
            "4. 태스크는 한국어로 출력할 것.\n"
            "5. **중요: 반드시 정확히 3개 이상 5개 이하의 태스크로 분해할 것. 절대로 6개 이상 생성하지 말 것. 너무 세분화하지 말고, 적절히 통합하여 최대 5개까지만 생성할 것.**\n"
            "목표: {query}"
        )
        chain = prompt | self.llm.with_structured_output(DecomposedTasks)
        result = chain.invoke({"query": query})

        log_and_print(f"✅ 목표 분해 완료: 총 {len(result.values)}개의 태스크 생성")
        for i, task in enumerate(result.values, 1):
            log_and_print(f"  태스크 {i}: {task[:80]}...")

        return result


# TaskExecutor 클래스: 개별 태스크를 실행하는 클래스
# Tavily 검색 도구를 사용하여 인터넷 조사를 수행하고 결과를 반환
class TaskExecutor:
    # 생성자: LLM과 검색 도구를 초기화
    def __init__(self, llm: ChatOpenAI):
        # LLM 인스턴스 저장
        self.llm = llm
        # Tavily 검색 도구 설정: 최대 3개의 검색 결과를 가져옴
        self.tools = [TavilySearchResults(max_results=3)]

    # run 메서드: 태스크를 받아 실행하고 결과를 문자열로 반환
    def run(self, task: str) -> str:
        # 로그: 현재 실행 중인 태스크 표시
        log_and_print(f"⚙️  태스크 실행 중: {task[:80]}...")

        # ReAct 에이전트 생성: Reasoning(사고) + Acting(행동) 패턴
        # LLM이 생각하고, 도구를 사용하고, 결과를 해석하는 과정을 반복
        agent = create_react_agent(self.llm, self.tools)

        # 에이전트 실행: 태스크를 수행하도록 요청
        result = agent.invoke(
            {
                "messages": [
                    (
                        "human",  # 사용자 메시지 역할
                        (
                            "다음 태스크를 실행하고 상세한 답변을 제공해 주세요.\n\n"
                            f"태스크: {task}\n\n"
                            "요건:\n"
                            "1. 필요에 따라 제공된 도구를 사용하세요.\n"
                            "2. 실행은 철저하고 포괄적으로 수행하세요.\n"
                            "3. 가능한 한 구체적인 사실이나 데이터를 제공하세요.\n"
                            "4. 발견한 내용을 명확하게 요약하세요.\n"
                        ),
                    )
                ]
            }
        )
        # 결과에서 최종 메시지의 내용 추출
        content = result["messages"][-1].content
        # 로그: 태스크 완료 및 결과 길이 표시
        log_and_print(f"  ✓ 태스크 완료 (결과 길이: {len(content)} 글자)")
        return content


# ResultAggregator 클래스: 모든 태스크 결과를 종합하여 최종 응답을 생성하는 클래스
# 여러 개의 조사 결과를 하나의 일관된 응답으로 통합
class ResultAggregator:
    # 생성자: LLM을 받아 초기화
    def __init__(self, llm: ChatOpenAI):
        # LLM 인스턴스 저장
        self.llm = llm

    # run 메서드: 목표, 응답 정의, 결과 리스트를 받아 최종 응답 생성
    def run(self, query: str, response_definition: str, results: list[str]) -> str:
        # 로그: 결과 집계 시작 알림
        log_and_print("📊 [단계 4] 결과 집계 시작")
        log_and_print(f"  수집된 결과 개수: {len(results)}개")

        # 프롬프트 템플릿 생성: 목표, 조사 결과, 응답 정의를 조합
        prompt = ChatPromptTemplate.from_template(
            "주어진 목표:\n{query}\n\n"
            "조사 결과:\n{results}\n\n"
            "주어진 목표에 대해 조사 결과를 활용하여 다음 지시에 기반한 응답을 생성해 주세요.\n"
            "{response_definition}"
        )

        # 결과 리스트를 하나의 문자열로 포맷팅
        # 각 결과에 번호를 붙여 "Info 1:", "Info 2:" 형식으로 구분
        results_str = "\n\n".join(
            f"Info {i+1}:\n{result}" for i, result in enumerate(results)
        )

        # 체인 생성: 프롬프트 → LLM → 문자열 파서
        # StrOutputParser()는 LLM 응답을 문자열로 변환
        chain = prompt | self.llm | StrOutputParser()

        # LLM 호출: 모든 정보를 종합하여 최종 응답 생성
        final_output = chain.invoke(
            {
                "query": query,  # 최적화된 목표
                "results": results_str,  # 포맷팅된 조사 결과
                "response_definition": response_definition,  # 응답 형식 정의
            }
        )

        # 로그: 결과 집계 완료 알림
        log_and_print(f"✅ 결과 집계 완료 (최종 결과 길이: {len(final_output)} 글자)")
        return final_output


# SinglePathPlanGeneration 클래스: Single Path 패턴의 전체 워크플로우를 관리하는 메인 클래스
# LangGraph를 사용하여 상태 기반 워크플로우를 구성하고 실행
# 워크플로우: 목표 설정 → 목표 분해 → 태스크 실행 (순차 반복) → 결과 집계
class SinglePathPlanGeneration:
    # 생성자: 필요한 모든 컴포넌트를 초기화하고 그래프를 생성
    def __init__(self, llm: ChatOpenAI):
        # 1단계를 위한 컴포넌트: 기본 목표 생성
        self.passive_goal_creator = PassiveGoalCreator(llm=llm)
        # 1단계를 위한 컴포넌트: 목표 최적화 (SMART 원칙)
        self.prompt_optimizer = PromptOptimizer(llm=llm)
        # 1단계를 위한 컴포넌트: 응답 형식 정의
        self.response_optimizer = ResponseOptimizer(llm=llm)
        # 2단계를 위한 컴포넌트: 목표를 태스크로 분해
        self.query_decomposer = QueryDecomposer(llm=llm)
        # 3단계를 위한 컴포넌트: 개별 태스크 실행
        self.task_executor = TaskExecutor(llm=llm)
        # 4단계를 위한 컴포넌트: 결과 집계
        self.result_aggregator = ResultAggregator(llm=llm)
        # LangGraph 워크플로우 그래프 생성 및 컴파일
        self.graph = self._create_graph()

    # _create_graph 메서드: LangGraph 워크플로우를 구성하는 내부 메서드
    # 노드(단계)들을 추가하고 엣지(연결)를 정의하여 실행 흐름을 구성
    def _create_graph(self) -> StateGraph:
        # StateGraph 생성: SinglePathPlanGenerationState를 상태 모델로 사용
        graph = StateGraph(SinglePathPlanGenerationState)

        # 노드 추가: 각 단계에 해당하는 함수를 노드로 등록
        graph.add_node("goal_setting", self._goal_setting)  # 1단계: 목표 설정
        graph.add_node("decompose_query", self._decompose_query)  # 2단계: 목표 분해
        graph.add_node("execute_task", self._execute_task)  # 3단계: 태스크 실행
        graph.add_node("aggregate_results", self._aggregate_results)  # 4단계: 결과 집계

        # 시작 노드 설정: goal_setting부터 시작
        graph.set_entry_point("goal_setting")

        # 엣지 추가: 노드 간의 실행 순서 정의
        # goal_setting → decompose_query (항상 이동)
        graph.add_edge("goal_setting", "decompose_query")
        # decompose_query → execute_task (항상 이동)
        graph.add_edge("decompose_query", "execute_task")

        # 조건부 엣지: execute_task 이후의 분기 처리
        # 아직 실행할 태스크가 남아있으면 execute_task로 돌아감 (순환)
        # 모든 태스크 완료 시 aggregate_results로 이동
        graph.add_conditional_edges(
            "execute_task",
            lambda state: state.current_task_index < len(state.tasks),  # 조건 함수
            {True: "execute_task", False: "aggregate_results"},  # True/False에 따른 다음 노드
        )

        # aggregate_results → END (워크플로우 종료)
        graph.add_edge("aggregate_results", END)

        # 그래프 컴파일: 정의된 워크플로우를 실행 가능한 형태로 변환
        return graph.compile()

    def _goal_setting(self, state: SinglePathPlanGenerationState) -> dict[str, Any]:
        log_and_print("🎯 [단계 1] 목표 설정 시작")
        log_and_print(f"  사용자 입력: {state.query}")

        # 1-1. 기본 목표 생성
        log_and_print("  → 기본 목표 생성 중...")
        goal: Goal = self.passive_goal_creator.run(query=state.query)
        log_and_print(f"  ✓ 기본 목표: {goal.text[:100]}...")

        # 1-2. 목표 최적화 (SMART 원칙)
        log_and_print("  → 목표 최적화 중 (SMART 원칙)...")
        optimized_goal: OptimizedGoal = self.prompt_optimizer.run(query=goal.text)
        log_and_print(f"  ✓ 최적화된 목표: {optimized_goal.description[:100]}...")
        log_and_print(f"  ✓ 측정 기준: {optimized_goal.metrics[:100]}...")

        # 1-3. 응답 형식 최적화
        log_and_print("  → 응답 형식 정의 중...")
        optimized_response: str = self.response_optimizer.run(query=optimized_goal.text)
        log_and_print(f"  ✓ 응답 형식 정의 완료")

        log_and_print("✅ [단계 1] 목표 설정 완료")
        log_and_print("")

        return {
            "optimized_goal": optimized_goal.text,
            "optimized_response": optimized_response,
        }

    def _decompose_query(self, state: SinglePathPlanGenerationState) -> dict[str, Any]:
        decomposed_tasks: DecomposedTasks = self.query_decomposer.run(
            query=state.optimized_goal
        )
        log_and_print("")
        return {"tasks": decomposed_tasks.values}

    def _execute_task(self, state: SinglePathPlanGenerationState) -> dict[str, Any]:
        current_task_num = state.current_task_index + 1
        total_tasks = len(state.tasks)

        if state.current_task_index == 0:
            log_and_print("🚀 [단계 3] 태스크 실행 시작")
            log_and_print("")

        log_and_print(f"📝 태스크 {current_task_num}/{total_tasks} 실행")
        current_task = state.tasks[state.current_task_index]
        result = self.task_executor.run(task=current_task)

        log_and_print("")

        return {
            "results": [result],
            "current_task_index": state.current_task_index + 1,
        }

    def _aggregate_results(
        self, state: SinglePathPlanGenerationState
    ) -> dict[str, Any]:
        log_and_print("✅ [단계 3] 모든 태스크 실행 완료")
        log_and_print("")

        final_output = self.result_aggregator.run(
            query=state.optimized_goal,
            response_definition=state.optimized_response,
            results=state.results,
        )
        return {"final_output": final_output}

    def run(self, query: str) -> str:
        log_and_print("=" * 80)
        log_and_print("🎬 Single Path Plan Generation 시작")
        log_and_print("=" * 80)
        log_and_print("")

        initial_state = SinglePathPlanGenerationState(query=query)
        final_state = self.graph.invoke(initial_state, {"recursion_limit": 1000})

        log_and_print("")
        log_and_print("=" * 80)
        log_and_print("🎉 Single Path Plan Generation 완료")
        log_and_print("=" * 80)

        return final_state.get("final_output", "최종 응답을 생성하지 못했습니다.")


# main 함수: Single-path plan generation 패턴으로 태스크를 실행하는 진입점
# Single-path: 하나의 직선적인 실행 경로를 따라 태스크를 순차적으로 수행
# 프로세스: 1) 목표 설정 → 2) 목표 분해 → 3) 순차 실행 → 4) 결과 집계
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
        # Single-path plan generation 방식으로 태스크 실행
        description="SinglePathPlanGeneration을 사용하여 태스크를 실행합니다"
    )
    # --task 인자 추가
    parser.add_argument("--task", type=str, required=True, help="실행할 태스크")
    # 커맨드 라인 인자 파싱
    args = parser.parse_args()

    # ChatOpenAI 인스턴스 생성
    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    # SinglePathPlanGeneration 에이전트 생성
    agent = SinglePathPlanGeneration(llm=llm)
    # 태스크 실행: 단일 경로로 순차적 실행
    result = agent.run(args.task)

    # 최종 결과 출력
    print("")
    print("=" * 80)
    print("📄 최종 결과")
    print("=" * 80)
    print(result)


# 스크립트가 직접 실행될 때만 main() 함수를 호출
if __name__ == "__main__":
    main()
