# operator 모듈: 연산자 함수를 제공 (여기서는 add를 Annotated 타입에 사용)
import operator
# datetime 모듈: 현재 날짜/시간 정보를 가져오기 위해 사용
from datetime import datetime
# typing 모듈: 타입 힌트를 위한 Annotated(메타데이터 포함 타입), Any(모든 타입) 임포트
from typing import Annotated, Any
# logging 모듈: 프로그램 실행 흐름을 추적하기 위한 로깅 기능
import logging

# common 모듈에서 Reflection 관련 클래스들 임포트
# Reflection: 성찰 데이터 모델, ReflectionManager: 성찰 데이터 관리, TaskReflector: 성찰 수행
from common.reflection_manager import Reflection, ReflectionManager, TaskReflector
# LangChain 커뮤니티 도구: Tavily 검색 엔진을 사용한 웹 검색 도구
from langchain_community.tools.tavily_search import TavilySearchResults
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


# format_reflections 함수: Reflection 객체 리스트를 XML 형식의 문자열로 포맷팅
# 과거 성찰 내용을 프롬프트에 포함시키기 위해 사용
def format_reflections(reflections: list[Reflection]) -> str:
    # 각 Reflection을 <ref_N> 태그로 감싸서 구조화
    # <task>와 <reflection> 태그로 내용을 명확히 구분
    return (
        "\n\n".join(
            f"<ref_{i}><task>{r.task}</task><reflection>{r.reflection}</reflection></ref_{i}>"
            for i, r in enumerate(reflections)
        )
        if reflections  # 성찰이 있으면 포맷팅된 문자열 반환
        else "No relevant past reflections."  # 없으면 기본 메시지
    )


# DecomposedTasks 클래스: 분해된 태스크들을 담는 컨테이너
# Self Reflection에서는 3~5개의 태스크로 분해
class DecomposedTasks(BaseModel):
    # values 필드: 태스크 문자열들의 리스트
    # min_items=3, max_items=5: 3~5개의 태스크로 분해하도록 제약
    values: list[str] = Field(
        default_factory=list,
        min_items=3,
        max_items=5,
        description="3~5개로 분해된 태스크",
    )


# ReflectiveAgentState 클래스: Self Reflection 워크플로우의 상태 관리
# 일반 State와 달리 reflection_ids와 retry_count 필드가 추가됨
class ReflectiveAgentState(BaseModel):
    # query 필드: 사용자가 최초에 입력한 쿼리
    query: str = Field(..., description="사용자가 처음에 입력한 쿼리")
    # optimized_goal 필드: SMART 원칙으로 최적화된 목표
    optimized_goal: str = Field(default="", description="최적화된 목표")
    # optimized_response 필드: 최종 응답의 형식과 구조에 대한 정의
    optimized_response: str = Field(
        default="", description="최적화된 응답 정의"
    )
    # tasks 필드: 분해된 태스크들의 리스트
    tasks: list[str] = Field(default_factory=list, description="실행할 태스크 목록")
    # current_task_index 필드: 현재 실행 중인 태스크의 인덱스
    current_task_index: int = Field(default=0, description="현재 실행 중인 태스크 번호")
    # results 필드: 각 태스크 실행 결과를 순차적으로 저장하는 리스트
    results: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="실행 완료된 태스크 결과 목록"
    )
    # reflection_ids 필드: 각 태스크의 성찰 결과 ID를 저장하는 리스트
    # Self Reflection의 핵심: 각 실행마다 성찰을 수행하고 ID를 기록
    reflection_ids: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="리플렉션 결과의 ID 목록"
    )
    # final_output 필드: 모든 태스크 완료 후 집계된 최종 출력
    final_output: str = Field(default="", description="최종 출력 결과")
    # retry_count 필드: 현재 태스크의 재시도 횟수
    # 성찰 결과 재시도가 필요하면 증가, 통과하면 0으로 리셋
    retry_count: int = Field(default=0, description="태스크 재시도 횟수")


class ReflectiveGoalCreator:
    def __init__(self, llm: ChatOpenAI, reflection_manager: ReflectionManager):
        self.llm = llm
        self.reflection_manager = reflection_manager
        self.passive_goal_creator = PassiveGoalCreator(llm=self.llm)
        self.prompt_optimizer = PromptOptimizer(llm=self.llm)

    def run(self, query: str) -> str:
        logger.info("🎯 [목표 설정] 과거 회고를 고려한 목표 생성 시작")
        relevant_reflections = self.reflection_manager.get_relevant_reflections(query)
        logger.info(f"  관련 과거 회고 {len(relevant_reflections)}개 발견")
        reflection_text = format_reflections(relevant_reflections)

        query = f"{query}\n\n목표 설정 시 다음의 과거 회고를 고려할 것:\n{reflection_text}"
        goal: Goal = self.passive_goal_creator.run(query=query)
        logger.info(f"  기본 목표 생성 완료: {goal.text[:100]}...")
        optimized_goal: OptimizedGoal = self.prompt_optimizer.run(query=goal.text)
        logger.info(f"  목표 최적화 완료")
        return optimized_goal.text


class ReflectiveResponseOptimizer:
    def __init__(self, llm: ChatOpenAI, reflection_manager: ReflectionManager):
        self.llm = llm
        self.reflection_manager = reflection_manager
        self.response_optimizer = ResponseOptimizer(llm=llm)

    def run(self, query: str) -> str:
        logger.info("📝 [응답 최적화] 과거 회고를 고려한 응답 형식 정의 시작")
        relevant_reflections = self.reflection_manager.get_relevant_reflections(query)
        logger.info(f"  관련 과거 회고 {len(relevant_reflections)}개 발견")
        reflection_text = format_reflections(relevant_reflections)

        query = f"{query}\n\n응답 최적화에 다음의 과거 회고를 고려할 것:\n{reflection_text}"
        optimized_response: str = self.response_optimizer.run(query=query)
        logger.info("  응답 형식 정의 완료")
        return optimized_response


class QueryDecomposer:
    def __init__(self, llm: ChatOpenAI, reflection_manager: ReflectionManager):
        self.llm = llm.with_structured_output(DecomposedTasks)
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.reflection_manager = reflection_manager

    def run(self, query: str) -> DecomposedTasks:
        logger.info("📋 [목표 분해] 과거 회고를 고려한 태스크 분해 시작")
        relevant_reflections = self.reflection_manager.get_relevant_reflections(query)
        logger.info(f"  관련 과거 회고 {len(relevant_reflections)}개 발견")
        reflection_text = format_reflections(relevant_reflections)
        prompt = ChatPromptTemplate.from_template(
            f"CURRENT_DATE: {self.current_date}\n"
            "-----\n"
            "태스크: 주어진 목표를 구체적이고 실행 가능한 태스크로 분해해 주세요.\n"
            "요건:\n"
            "1. 다음 행동만으로 목표를 달성할 것. 절대 지정된 것 외의 행동을 취하지 말 것.\n"
            "   - 인터넷을 이용하여 목표 달성을 위한 조사를 수행한다.\n"
            "2. 각 태스크는 구체적이고 상세하게 작성되어 있으며, 독립적으로 실행 및 검증 가능한 정보를 포함할 것. 추상적인 표현을 전혀 포함하지 않을 것.\n"
            "3. 태스크는 실행 가능한 순서로 나열할 것.\n"
            "4. 태스크는 한국어로 출력할 것.\n"
            "5. 태스크를 작성할 때 다음의 과거 회고를 고려할 것:\n{reflections}\n\n"
            "목표: {query}"
        )
        chain = prompt | self.llm
        tasks = chain.invoke({"query": query, "reflections": reflection_text})
        logger.info(f"  태스크 분해 완료: 총 {len(tasks.values)}개의 태스크 생성")
        for i, task in enumerate(tasks.values, 1):
            logger.info(f"    태스크 {i}: {task[:80]}...")
        return tasks


class TaskExecutor:
    def __init__(self, llm: ChatOpenAI, reflection_manager: ReflectionManager):
        self.llm = llm
        self.reflection_manager = reflection_manager
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.tools = [TavilySearchResults(max_results=3)]

    def run(self, task: str) -> str:
        logger.info(f"⚙️  [태스크 실행] 시작: {task[:80]}...")
        relevant_reflections = self.reflection_manager.get_relevant_reflections(task)
        logger.info(f"  관련 과거 회고 {len(relevant_reflections)}개 적용")
        reflection_text = format_reflections(relevant_reflections)
        agent = create_react_agent(self.llm, self.tools)
        result = agent.invoke(
            {
                "messages": [
                    (
                        "human",
                        f"CURRENT_DATE: {self.current_date}\n"
                        "-----\n"
                        f"다음 태스크를 실행하고 상세한 답변을 제공해 주세요.\n\n태스크: {task}\n\n"
                        "요건:\n"
                        "1. 필요에 따라 제공된 도구를 사용할 것.\n"
                        "2. 실행 시 철저하고 포괄적일 것.\n"
                        "3. 가능한 한 구체적인 사실과 데이터를 제공할 것.\n"
                        "4. 발견 사항을 명확하게 요약할 것.\n"
                        f"5. 다음의 과거 회고를 고려할 것:\n{reflection_text}\n",
                    )
                ]
            }
        )
        content = result["messages"][-1].content
        logger.info(f"  태스크 실행 완료 (결과 길이: {len(content)} 글자)")
        return content


class ResultAggregator:
    def __init__(self, llm: ChatOpenAI, reflection_manager: ReflectionManager):
        self.llm = llm
        self.reflection_manager = reflection_manager
        self.current_date = datetime.now().strftime("%Y-%m-%d")

    def run(
        self,
        query: str,
        results: list[str],
        reflection_ids: list[str],
        response_definition: str,
    ) -> str:
        logger.info("📊 [결과 집계] 과거 회고를 반영한 최종 결과 생성 시작")
        logger.info(f"  수집된 결과 개수: {len(results)}개")
        logger.info(f"  참조할 회고 개수: {len(reflection_ids)}개")
        relevant_reflections = [
            self.reflection_manager.get_reflection(rid) for rid in reflection_ids
        ]
        prompt = ChatPromptTemplate.from_template(
            "주어진 목표:\n{query}\n\n"
            "조사 결과:\n{results}\n\n"
            "주어진 목표에 대해 조사 결과를 이용하여 다음 지시에 기반한 응답을 생성해 주세요.\n"
            "{response_definition}\n\n"
            "과거 회고를 고려할 것:\n{reflection_text}\n"
        )
        chain = prompt | self.llm | StrOutputParser()
        final_output = chain.invoke(
            {
                "query": query,
                "results": "\n\n".join(
                    f"정보 {i+1}:\n{result}" for i, result in enumerate(results)
                ),
                "response_definition": response_definition,
                "reflection_text": format_reflections(relevant_reflections),
            }
        )
        logger.info(f"  결과 집계 완료 (최종 결과 길이: {len(final_output)} 글자)")
        return final_output


class ReflectiveAgent:
    def __init__(
        self,
        llm: ChatOpenAI,
        reflection_manager: ReflectionManager,
        task_reflector: TaskReflector,
        max_retries: int = 2,
    ):
        self.reflection_manager = reflection_manager
        self.task_reflector = task_reflector
        self.reflective_goal_creator = ReflectiveGoalCreator(
            llm=llm, reflection_manager=self.reflection_manager
        )
        self.reflective_response_optimizer = ReflectiveResponseOptimizer(
            llm=llm, reflection_manager=self.reflection_manager
        )
        self.query_decomposer = QueryDecomposer(
            llm=llm, reflection_manager=self.reflection_manager
        )
        self.task_executor = TaskExecutor(
            llm=llm, reflection_manager=self.reflection_manager
        )
        self.result_aggregator = ResultAggregator(
            llm=llm, reflection_manager=self.reflection_manager
        )
        self.max_retries = max_retries
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        graph = StateGraph(ReflectiveAgentState)
        graph.add_node("goal_setting", self._goal_setting)
        graph.add_node("decompose_query", self._decompose_query)
        graph.add_node("execute_task", self._execute_task)
        graph.add_node("reflect_on_task", self._reflect_on_task)
        graph.add_node("update_task_index", self._update_task_index)
        graph.add_node("aggregate_results", self._aggregate_results)
        graph.set_entry_point("goal_setting")
        graph.add_edge("goal_setting", "decompose_query")
        graph.add_edge("decompose_query", "execute_task")
        graph.add_edge("execute_task", "reflect_on_task")
        graph.add_conditional_edges(
            "reflect_on_task",
            self._should_retry_or_continue,
            {
                "retry": "execute_task",
                "continue": "update_task_index",
                "finish": "aggregate_results",
            },
        )
        graph.add_edge("update_task_index", "execute_task")
        graph.add_edge("aggregate_results", END)
        return graph.compile()

    def _goal_setting(self, state: ReflectiveAgentState) -> dict[str, Any]:
        logger.info("=" * 80)
        logger.info("🎯 [1단계: 목표 설정] 시작")
        logger.info("=" * 80)
        optimized_goal: str = self.reflective_goal_creator.run(query=state.query)
        optimized_response: str = self.reflective_response_optimizer.run(
            query=optimized_goal
        )
        logger.info("✅ [1단계: 목표 설정] 완료\n")
        return {
            "optimized_goal": optimized_goal,
            "optimized_response": optimized_response,
        }

    def _decompose_query(self, state: ReflectiveAgentState) -> dict[str, Any]:
        logger.info("=" * 80)
        logger.info("📋 [2단계: 목표 분해] 시작")
        logger.info("=" * 80)
        tasks: DecomposedTasks = self.query_decomposer.run(query=state.optimized_goal)
        logger.info("✅ [2단계: 목표 분해] 완료\n")
        return {"tasks": tasks.values}

    def _execute_task(self, state: ReflectiveAgentState) -> dict[str, Any]:
        current_task_num = state.current_task_index + 1
        total_tasks = len(state.tasks)
        if state.retry_count > 0:
            logger.info(f"🔄 [재시도 {state.retry_count}회차] 태스크 {current_task_num}/{total_tasks} 재실행")
        else:
            logger.info(f"📝 [3단계: 태스크 실행] 태스크 {current_task_num}/{total_tasks} 실행")
        current_task = state.tasks[state.current_task_index]
        result = self.task_executor.run(task=current_task)
        return {"results": [result], "current_task_index": state.current_task_index}

    def _reflect_on_task(self, state: ReflectiveAgentState) -> dict[str, Any]:
        logger.info(f"🔍 [자기 성찰] 태스크 {state.current_task_index + 1} 결과 검토 중...")
        current_task = state.tasks[state.current_task_index]
        current_result = state.results[-1]
        reflection = self.task_reflector.run(task=current_task, result=current_result)

        if reflection.judgment.needs_retry:
            logger.info(f"  ⚠️  재시도 필요: {', '.join(reflection.judgment.reasons)}")
        else:
            logger.info(f"  ✅ 성찰 통과")

        logger.info(f"  성찰 내용: {reflection.reflection[:100]}...\n")

        return {
            "reflection_ids": [reflection.id],
            "retry_count": (
                state.retry_count + 1 if reflection.judgment.needs_retry else 0
            ),
        }

    def _should_retry_or_continue(self, state: ReflectiveAgentState) -> str:
        latest_reflection_id = state.reflection_ids[-1]
        latest_reflection = self.reflection_manager.get_reflection(latest_reflection_id)
        if (
            latest_reflection
            and latest_reflection.judgment.needs_retry
            and state.retry_count < self.max_retries
        ):
            logger.info(f"↩️  재시도 결정: 현재 재시도 횟수 {state.retry_count}/{self.max_retries}")
            return "retry"
        elif state.current_task_index < len(state.tasks) - 1:
            logger.info("➡️  다음 태스크로 진행")
            return "continue"
        else:
            logger.info("✅ 모든 태스크 완료\n")
            return "finish"

    def _update_task_index(self, state: ReflectiveAgentState) -> dict[str, Any]:
        logger.info(f"📌 태스크 인덱스 업데이트: {state.current_task_index} → {state.current_task_index + 1}\n")
        return {"current_task_index": state.current_task_index + 1}

    def _aggregate_results(self, state: ReflectiveAgentState) -> dict[str, Any]:
        logger.info("=" * 80)
        logger.info("📊 [4단계: 결과 집계] 시작")
        logger.info("=" * 80)
        final_output = self.result_aggregator.run(
            query=state.optimized_goal,
            results=state.results,
            reflection_ids=state.reflection_ids,
            response_definition=state.optimized_response,
        )
        logger.info("✅ [4단계: 결과 집계] 완료\n")
        return {"final_output": final_output}

    def run(self, query: str) -> str:
        logger.info("=" * 80)
        logger.info("🎬 Self-Reflection Agent 시작")
        logger.info("=" * 80)
        logger.info(f"사용자 쿼리: {query}\n")
        initial_state = ReflectiveAgentState(query=query)
        final_state = self.graph.invoke(initial_state, {"recursion_limit": 1000})
        logger.info("=" * 80)
        logger.info("🎉 Self-Reflection Agent 완료")
        logger.info("=" * 80)
        return final_state.get("final_output", "오류: 출력에 실패했습니다.")


# main 함수: Self-reflection 패턴을 구현하는 진입점
# Self-reflection: 에이전트가 자신의 수행 결과를 돌아보고 개선하는 패턴
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
        # Self-reflection 방식으로 태스크를 실행한다는 설명
        description="ReflectiveAgent를 사용해 태스크를 실행합니다(Self-reflection)"
    )
    # --task 인자 추가
    parser.add_argument("--task", type=str, required=True, help="실행할 태스크")
    # 커맨드 라인 인자 파싱
    args = parser.parse_args()

    # ChatOpenAI 인스턴스 생성
    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )
    # ReflectionManager 초기화: 리플렉션 데이터를 파일에 저장하고 관리
    # file_path: Self-reflection 데이터를 저장할 JSON 파일 경로
    reflection_manager = ReflectionManager(file_path="tmp/self_reflection_db.json")
    # TaskReflector 초기화: 태스크 수행 후 리플렉션을 수행하는 역할
    # 같은 LLM을 사용하여 자기 성찰 (Self-reflection)
    task_reflector = TaskReflector(llm=llm, reflection_manager=reflection_manager)
    # ReflectiveAgent 초기화: 자기 성찰 기능을 가진 에이전트 생성
    agent = ReflectiveAgent(
        llm=llm, reflection_manager=reflection_manager, task_reflector=task_reflector
    )
    # 태스크 실행: 수행 → 성찰 → 필요시 재시도의 반복적 프로세스
    result = agent.run(args.task)
    # 최종 결과 출력
    print(result)


# 스크립트가 직접 실행될 때만 main() 함수를 호출
if __name__ == "__main__":
    main()
