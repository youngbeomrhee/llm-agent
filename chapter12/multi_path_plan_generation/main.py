# operator 모듈: 연산자 함수를 제공 (여기서는 add를 Annotated 타입에 사용)
import operator
# datetime 모듈: 현재 날짜/시간 정보를 가져오기 위해 사용
from datetime import datetime
# logging 모듈: 실행 흐름 추적을 위한 로깅
import logging
# typing 모듈: 타입 힌트를 위한 Annotated(메타데이터 포함 타입), Any(모든 타입) 임포트
from typing import Annotated, Any

# 로거 설정: 실행 흐름을 추적하기 위한 로깅 시스템 구성
logger = logging.getLogger(__name__)  # 현재 모듈의 로거 인스턴스 생성

# LangChain 커뮤니티 도구: Tavily 검색 엔진을 사용한 웹 검색 도구
from langchain_community.tools.tavily_search import TavilySearchResults
# LangChain 출력 파서: LLM 출력을 문자열로 변환하는 파서
from langchain_core.output_parsers import StrOutputParser
# LangChain 프롬프트 템플릿: 대화형 프롬프트를 생성하기 위한 템플릿 클래스
from langchain_core.prompts import ChatPromptTemplate
# LangChain Runnable: 실행 시 설정 가능한 필드를 정의하기 위한 클래스
from langchain_core.runnables import ConfigurableField
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


# TaskOption 클래스: 각 태스크에 대한 구체적인 실행 옵션을 나타내는 모델
# Multi-path planning에서 하나의 태스크를 수행할 수 있는 여러 방법 중 하나
class TaskOption(BaseModel):
    # description 필드: 해당 옵션에 대한 구체적인 설명
    description: str = Field(default="", description="태스크 옵션에 대한 설명")


# Task 클래스: 하나의 고수준 태스크와 그 태스크를 수행하는 여러 옵션을 포함
# Multi-path planning의 핵심: 각 태스크마다 여러 접근 방법(옵션)을 가질 수 있음
class Task(BaseModel):
    # task_name 필드: 태스크의 이름 또는 설명 (필수 필드)
    task_name: str = Field(..., description="태스크 이름")
    # options 필드: 이 태스크를 수행할 수 있는 2~3개의 서로 다른 접근 방법
    # min_items=2, max_items=3: LLM이 각 태스크당 2~3개의 옵션을 생성하도록 제약
    options: list[TaskOption] = Field(
        default_factory=list,
        min_items=2,
        max_items=3,
        description="2~3개의 태스크 옵션",
    )


# DecomposedTasks 클래스: 전체 목표를 분해한 여러 태스크들의 컨테이너
# 목표 달성을 위한 3~5개의 단계별 태스크 리스트
class DecomposedTasks(BaseModel):
    # values 필드: Task 객체들의 리스트
    # min_items=3, max_items=5: 목표를 3~5개의 태스크로 분해하도록 제약
    values: list[Task] = Field(
        default_factory=list,
        min_items=3,
        max_items=5,
        description="3~5개로 분해된 태스크",
    )


# MultiPathPlanGenerationState 클래스: 전체 워크플로우의 상태를 관리하는 모델
# LangGraph의 StateGraph에서 사용되며, 각 노드 간 데이터 전달을 담당
class MultiPathPlanGenerationState(BaseModel):
    # query 필드: 사용자가 최초에 입력한 쿼리 (필수)
    query: str = Field(..., description="사용자가 입력한 쿼리")
    # optimized_goal 필드: SMART 원칙으로 최적화된 목표
    optimized_goal: str = Field(default="", description="최적화된 목표")
    # optimized_response 필드: 최종 응답의 형식과 구조에 대한 정의
    optimized_response: str = Field(default="", description="최적화된 응답")
    # tasks 필드: 분해된 태스크들의 리스트 (각 태스크는 여러 옵션 포함)
    tasks: DecomposedTasks = Field(
        default_factory=DecomposedTasks,
        description="여러 옵션을 가진 태스크 리스트",
    )
    # current_task_index 필드: 현재 실행 중인 태스크의 인덱스 (0부터 시작)
    current_task_index: int = Field(default=0, description="현재 태스크의 인덱스")
    # chosen_options 필드: 각 태스크에서 선택된 옵션의 인덱스 리스트
    # Annotated[list[int], operator.add]: 새로운 값이 추가될 때 기존 리스트에 append
    chosen_options: Annotated[list[int], operator.add] = Field(
        default_factory=list, description="각 태스크에서 선택된 옵션의 인덱스"
    )
    # results 필드: 각 태스크 실행 결과를 순차적으로 저장하는 리스트
    # Annotated[list[str], operator.add]: 새로운 결과가 기존 리스트에 추가됨
    results: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="실행된 태스크의 결과"
    )
    # final_output 필드: 모든 태스크 완료 후 집계된 최종 출력
    final_output: str = Field(default="", description="최종 출력")


# QueryDecomposer 클래스: 목표를 여러 개의 실행 가능한 태스크로 분해하는 클래스
# Multi-path planning의 첫 단계: 목표 분해 + 각 태스크에 여러 옵션 생성
class QueryDecomposer:
    # 생성자: LLM을 받아 초기화
    def __init__(self, llm: ChatOpenAI):
        # LLM 인스턴스 저장
        self.llm = llm
        # 현재 날짜를 YYYY-MM-DD 형식으로 저장 (프롬프트에 컨텍스트로 제공)
        self.current_date = datetime.now().strftime("%Y-%m-%d")

    # run 메서드: 쿼리를 받아 DecomposedTasks 객체로 분해하여 반환
    def run(self, query: str) -> DecomposedTasks:
        logger.info(f"[QueryDecomposer] 쿼리 분해 시작: {query}")
        prompt = ChatPromptTemplate.from_template(
            f"CURRENT_DATE: {self.current_date}\n"
            "-----\n"
            "태스크: 주어진 목표를 3~5개의 고수준 태스크로 분해하고, 각 태스크에 2~3개의 구체적인 옵션을 제공하세요.\n"
            "요구사항:\n"
            "1. 다음 행동만으로 목표를 달성할 것. 절대 지정된 것 외의 행동을 취하지 말 것.\n"
            "   - 인터넷을 이용하여 목표 달성을 위한 조사를 수행.\n"
            "2. 각 고수준 태스크는 구체적이고 상세하게 기술되어야 하며, 독립적으로 실행 및 검증 가능한 정보를 포함할 것. 추상적인 표현을 전혀 포함하지 말 것.\n"
            "3. 각 항목 레벨 태스크에 2~3개의 다른 접근법이나 옵션을 제공할 것.\n"
            "4. 태스크는 실행 가능한 순서로 나열할 것.\n"
            "5. 태스크는 한국어로 출력할 것.\n\n"
            "기억하세요: 실행할 수 없는 태스크와 선택지는 절대로 만들지 마세요.\n\n"
            "목표: {query}"
        )
        chain = prompt | self.llm.with_structured_output(DecomposedTasks)
        result = chain.invoke({"query": query})
        logger.info(f"[QueryDecomposer] {len(result.values)}개의 태스크로 분해 완료")
        for i, task in enumerate(result.values, 1):
            logger.info(f"[QueryDecomposer]   태스크 {i}: {task.task_name} ({len(task.options)}개 옵션)")
        return result


# OptionPresenter 클래스: 각 태스크의 옵션을 제시하고 LLM이 최적의 옵션을 선택하도록 하는 클래스
# Multi-path planning의 핵심: 각 태스크마다 여러 접근 방법 중 하나를 동적으로 선택
class OptionPresenter:
    # 생성자: LLM을 받아 초기화하고 max_tokens를 동적으로 설정할 수 있도록 구성
    def __init__(self, llm: ChatOpenAI):
        # configurable_fields: LLM의 특정 파라미터를 런타임에 변경 가능하도록 설정
        # max_tokens를 동적으로 설정하여 옵션 선택 시 1토큰만 사용하도록 제한 가능
        self.llm = llm.configurable_fields(
            max_tokens=ConfigurableField(id="max_tokens")  # max_tokens를 설정 가능한 필드로 등록
        )

    # run 메서드: 태스크의 옵션을 제시하고 LLM이 최적의 옵션을 선택하도록 함
    # 반환값: 선택된 옵션의 인덱스 (0부터 시작)
    def run(self, task: Task) -> int:
        # 태스크 정보 추출
        task_name = task.task_name  # 태스크 이름 (예: "AI agent의 정의를 조사한다")
        options = task.options  # 2~3개의 TaskOption 객체 리스트

        # 로그 및 콘솔에 옵션 출력
        logger.info(f"[OptionPresenter] 옵션 제시 - 태스크: {task_name}")
        print(f"\n태스크: {task_name}")
        for i, option in enumerate(options):
            # 사용자에게 옵션을 번호와 함께 표시 (1부터 시작)
            print(f"{i + 1}. {option.description}")
            logger.info(f"[OptionPresenter]   옵션 {i+1}: {option.description}")

        # LLM에게 옵션 선택을 요청하는 프롬프트 생성
        choice_prompt = ChatPromptTemplate.from_template(
            "태스크: 주어진 태스크와 옵션을 기반으로 최적의 옵션을 선택하세요. 반드시 번호만으로 답변하세요.\n\n"
            "참고로, 당신은 다음 행동만 할 수 있습니다.\n"
            "- 인터넷을 이용하여 목표 달성을 위한 조사를 수행.\n\n"
            "태스크: {task_name}\n"
            "옵션:\n{options_text}\n"
            "선택 (1-{num_options}): "
        )

        # 옵션들을 텍스트로 포맷팅 (1번부터 시작하는 리스트)
        options_text = "\n".join(
            f"{i+1}. {option.description}" for i, option in enumerate(options)
        )

        # LCEL(LangChain Expression Language) 체인 구성
        # 1. choice_prompt: 옵션 선택 프롬프트
        # 2. self.llm.with_config(configurable=dict(max_tokens=1)): max_tokens=1로 제한하여 숫자만 반환
        #    - 이유: "1", "2", "3" 등 한 글자만 필요하므로 토큰 낭비 방지 및 응답 속도 향상
        # 3. StrOutputParser(): LLM 출력을 문자열로 변환
        chain = (
            choice_prompt
            | self.llm.with_config(configurable=dict(max_tokens=1))  # 1토큰만 생성 (숫자만 반환)
            | StrOutputParser()  # 출력을 문자열로 파싱
        )

        # 체인 실행: LLM이 옵션 번호를 선택
        choice_str = chain.invoke(
            {
                "task_name": task_name,
                "options_text": options_text,
                "num_options": len(options),
            }
        )

        # 사용자와 로그에 선택 결과 출력
        print(f"==> 에이전트의 선택: {choice_str}\n")

        # 선택된 번호를 인덱스로 변환 (1번 선택 → 인덱스 0)
        choice_idx = int(choice_str.strip()) - 1
        logger.info(f"[OptionPresenter] 선택된 옵션: {choice_idx + 1} - {options[choice_idx].description}")

        return choice_idx  # 선택된 옵션의 인덱스 반환 (0, 1, 또는 2)


# TaskExecutor 클래스: 선택된 옵션에 따라 태스크를 실제로 실행하는 클래스
# ReAct 패턴의 에이전트를 사용하여 도구(검색 등)를 활용하며 태스크 수행
class TaskExecutor:
    # 생성자: LLM과 도구를 초기화
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm  # 추론과 행동 결정을 위한 LLM
        # TavilySearchResults: 웹 검색 도구 (최대 3개의 검색 결과 반환)
        self.tools = [TavilySearchResults(max_results=3)]

    # run 메서드: 태스크와 선택된 옵션을 실행하여 결과 반환
    # 매개변수:
    #   - task: 실행할 Task 객체
    #   - chosen_option: 선택된 TaskOption 객체 (구체적인 접근 방법)
    # 반환값: 태스크 실행 결과 (문자열)
    def run(self, task: Task, chosen_option: TaskOption) -> str:
        # 실행 시작 로그
        logger.info(f"[TaskExecutor] 태스크 실행 시작 - {task.task_name}")
        logger.info(f"[TaskExecutor] 선택된 접근법: {chosen_option.description}")

        # ReAct 에이전트 생성
        # create_react_agent: LangGraph의 미리 빌드된 함수로 Thought-Action-Observation 사이클 구현
        # - LLM이 생각(Thought)하고, 도구를 사용(Action)하며, 결과를 관찰(Observation)하는 과정 반복
        # - 최종 답변에 도달할 때까지 자동으로 반복
        agent = create_react_agent(self.llm, self.tools)

        # 에이전트 실행
        # messages 형식: [("role", "content")] - 대화 형식으로 입력 전달
        result = agent.invoke(
            {
                "messages": [
                    (
                        "human",  # 사용자 역할
                        # 태스크 실행 지시사항을 상세히 전달
                        f"다음 태스크를 실행하고 상세한 답변을 제공해주세요:\n\n"
                        f"태스크: {task.task_name}\n"  # 고수준 태스크 설명
                        f"선택된 접근법: {chosen_option.description}\n\n"  # 구체적인 실행 방법
                        f"요구사항:\n"
                        f"1. 필요에 따라 제공된 도구를 사용할 것.\n"  # 검색 도구 활용 허용
                        f"2. 실행에 있어 철저하고 포괄적일 것.\n"  # 충분한 정보 수집 요구
                        f"3. 가능한 한 구체적인 사실이나 데이터를 제공할 것.\n"  # 환각(hallucination) 방지
                        f"4. 발견 사항을 명확하게 요약할 것.\n",  # 결과의 명확성 요구
                    )
                ]
            }
        )

        # 결과 추출: messages 리스트의 마지막 메시지가 에이전트의 최종 답변
        # result["messages"][-1]: 대화 기록의 마지막 메시지 (AIMessage 객체)
        # .content: 메시지의 텍스트 내용
        content = result["messages"][-1].content
        logger.info(f"[TaskExecutor] 태스크 실행 완료 - 결과 길이: {len(content)} 글자")
        return content  # 태스크 실행 결과 문자열 반환


# ResultAggregator 클래스: 모든 태스크의 결과를 종합하여 최종 응답을 생성하는 클래스
# 각 태스크의 개별 결과를 하나의 일관된 응답으로 통합하고 응답 형식에 맞게 재구성
class ResultAggregator:
    # 생성자: LLM을 받아 초기화
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm  # 결과 통합 및 응답 생성을 위한 LLM

    # run 메서드: 모든 태스크의 결과를 집계하여 최종 응답 생성
    # 매개변수:
    #   - query: 최적화된 목표 (SMART 원칙 적용)
    #   - response_definition: ResponseOptimizer가 정의한 응답 형식
    #   - tasks: 실행된 Task 객체들의 리스트
    #   - chosen_options: 각 태스크에서 선택된 옵션의 인덱스 리스트
    #   - results: 각 태스크의 실행 결과 문자열 리스트
    # 반환값: 최종 통합 응답 (문자열)
    def run(
        self,
        query: str,
        response_definition: str,
        tasks: list[Task],
        chosen_options: list[int],
        results: list[str],
    ) -> str:
        logger.info(f"[ResultAggregator] 결과 집계 시작 - {len(results)}개의 태스크 결과 통합")

        # LLM에게 결과 통합을 지시하는 프롬프트 생성
        prompt = ChatPromptTemplate.from_template(
            "주어진 목표:\n{query}\n\n"  # 최적화된 목표 (SMART 원칙 적용)
            "조사 결과:\n{task_results}\n\n"  # 모든 태스크의 결과를 포맷팅한 텍스트
            "주어진 목표에 대해 조사 결과를 활용하여 다음 지시에 따라 응답을 생성하세요.\n"
            "{response_definition}"  # ResponseOptimizer가 정의한 응답 형식 및 평가 기준
        )

        # 태스크 결과를 읽기 쉬운 형식으로 포맷팅
        # 형식: 태스크 N: [태스크명]\n선택된 접근법: [옵션 설명]\n결과: [실행 결과]\n\n
        task_results = self._format_task_results(tasks, chosen_options, results)

        # LCEL 체인 구성: 프롬프트 → LLM → 문자열 파서
        chain = prompt | self.llm | StrOutputParser()

        # 체인 실행: 모든 정보를 종합하여 최종 응답 생성
        final_output = chain.invoke(
            {
                "query": query,  # 최적화된 목표
                "task_results": task_results,  # 포맷팅된 태스크 결과들
                "response_definition": response_definition,  # 응답 형식 정의
            }
        )

        logger.info(f"[ResultAggregator] 결과 집계 완료 - 최종 출력 길이: {len(final_output)} 글자")
        return final_output  # 최종 통합 응답 반환

    # _format_task_results 메서드: 태스크 결과를 구조화된 텍스트로 포맷팅
    # @staticmethod: 인스턴스 변수(self)를 사용하지 않으므로 정적 메서드로 선언
    # 매개변수:
    #   - tasks: Task 객체 리스트
    #   - chosen_options: 선택된 옵션 인덱스 리스트
    #   - results: 실행 결과 문자열 리스트
    # 반환값: 포맷팅된 결과 문자열
    @staticmethod
    def _format_task_results(
        tasks: list[Task], chosen_options: list[int], results: list[str]
    ) -> str:
        task_results = ""  # 결과를 담을 문자열 초기화

        # zip: 세 개의 리스트를 동시에 순회
        # enumerate: 인덱스와 값을 함께 반환 (i는 0부터 시작)
        for i, (task, chosen_option, result) in enumerate(
            zip(tasks, chosen_options, results)
        ):
            task_name = task.task_name  # 태스크 이름
            # chosen_option은 인덱스(0, 1, 2)이므로 task.options[chosen_option]으로 실제 옵션 가져오기
            chosen_option_desc = task.options[chosen_option].description

            # 구조화된 형식으로 결과 추가
            task_results += f"태스크 {i+1}: {task_name}\n"  # 태스크 번호와 이름 (1부터 시작)
            task_results += f"선택된 접근법: {chosen_option_desc}\n"  # 선택된 옵션 설명
            task_results += f"결과: {result}\n\n"  # 태스크 실행 결과 (빈 줄로 구분)

        return task_results  # 포맷팅된 결과 문자열 반환


# MultiPathPlanGeneration 클래스: Multi-Path Plan Generation 워크플로우의 메인 클래스
# LangGraph를 사용하여 5단계 워크플로우를 구성하고 실행
# 단계: 1.목표 설정 → 2.쿼리 분해 → 3.옵션 제시 → 4.태스크 실행 (반복) → 5.결과 집계
class MultiPathPlanGeneration:
    # 생성자: LLM과 각 단계를 담당하는 컴포넌트들을 초기화하고 워크플로우 그래프 생성
    def __init__(
        self,
        llm: ChatOpenAI,
    ):
        self.llm = llm  # 모든 컴포넌트에서 사용할 LLM 인스턴스

        # 각 단계를 처리하는 컴포넌트 초기화
        self.passive_goal_creator = PassiveGoalCreator(llm=self.llm)  # 1단계: 기본 목표 생성
        self.prompt_optimizer = PromptOptimizer(llm=self.llm)  # 1단계: SMART 원칙으로 목표 최적화
        self.response_optimizer = ResponseOptimizer(llm=self.llm)  # 1단계: 응답 형식 정의
        self.query_decomposer = QueryDecomposer(llm=self.llm)  # 2단계: 목표를 태스크+옵션으로 분해
        self.option_presenter = OptionPresenter(llm=self.llm)  # 3단계: 옵션 제시 및 선택
        self.task_executor = TaskExecutor(llm=self.llm)  # 4단계: 선택된 옵션으로 태스크 실행
        self.result_aggregator = ResultAggregator(llm=self.llm)  # 5단계: 모든 결과 통합

        # LangGraph 워크플로우 생성 (5단계 노드와 엣지 구성)
        self.graph = self._create_graph()

    # _create_graph 메서드: LangGraph StateGraph를 생성하고 워크플로우 구성
    # 반환값: 컴파일된 StateGraph 객체
    def _create_graph(self) -> StateGraph:
        # StateGraph 초기화: MultiPathPlanGenerationState를 상태 모델로 사용
        graph = StateGraph(MultiPathPlanGenerationState)

        # 5개의 노드(단계) 추가: (노드 이름, 실행 함수)
        graph.add_node("goal_setting", self._goal_setting)  # 1단계: 목표 설정
        graph.add_node("decompose_query", self._decompose_query)  # 2단계: 쿼리 분해
        graph.add_node("present_options", self._present_options)  # 3단계: 옵션 제시 (반복됨)
        graph.add_node("execute_task", self._execute_task)  # 4단계: 태스크 실행 (반복됨)
        graph.add_node("aggregate_results", self._aggregate_results)  # 5단계: 결과 집계

        # 진입점 설정: 워크플로우의 시작 노드
        graph.set_entry_point("goal_setting")

        # 엣지(노드 간 연결) 추가: 고정된 순서로 진행
        graph.add_edge("goal_setting", "decompose_query")  # 1단계 → 2단계
        graph.add_edge("decompose_query", "present_options")  # 2단계 → 3단계
        graph.add_edge("present_options", "execute_task")  # 3단계 → 4단계

        # 조건부 엣지: execute_task 후 분기 결정
        # - 아직 실행할 태스크가 남아있으면 (current_task_index < len(tasks)) → present_options로 돌아가기 (반복)
        # - 모든 태스크를 완료했으면 (current_task_index >= len(tasks)) → aggregate_results로 이동 (종료)
        graph.add_conditional_edges(
            "execute_task",  # 조건 체크할 노드
            lambda state: state.current_task_index < len(state.tasks.values),  # 조건 함수
            {True: "present_options", False: "aggregate_results"},  # True면 반복, False면 종료
        )

        # 최종 엣지: aggregate_results 완료 후 END (종료)
        graph.add_edge("aggregate_results", END)

        # 그래프 컴파일: 실행 가능한 형태로 변환
        return graph.compile()

    # _goal_setting 메서드: 1단계 - 목표 설정 노드
    # 사용자 쿼리를 SMART 원칙에 따라 최적화하고 응답 형식을 정의
    # 매개변수: state - 현재 상태 (query 필드 사용)
    # 반환값: State 업데이트용 딕셔너리 (optimized_goal, optimized_response)
    def _goal_setting(self, state: MultiPathPlanGenerationState) -> dict[str, Any]:
        logger.info("[MultiPathPlanGeneration] 1단계: 목표 설정 시작")

        # 1-1. 기본 목표 생성: 사용자 쿼리를 실행 가능한 목표로 변환
        goal: Goal = self.passive_goal_creator.run(query=state.query)
        logger.info(f"[MultiPathPlanGeneration] 목표 생성 완료: {goal.text}")

        # 1-2. 목표 최적화: SMART 원칙 (Specific, Measurable, Achievable, Relevant, Time-bound) 적용
        optimized_goal: OptimizedGoal = self.prompt_optimizer.run(query=goal.text)
        logger.info(f"[MultiPathPlanGeneration] 목표 최적화 완료: {optimized_goal.text}")

        # 1-3. 응답 형식 최적화: 최종 응답의 구조, 톤, 평가 기준 정의
        optimized_response: str = self.response_optimizer.run(query=optimized_goal.text)
        logger.info(f"[MultiPathPlanGeneration] 응답 형식 최적화 완료")

        # State 업데이트: 최적화된 목표와 응답 형식을 State에 저장
        return {
            "optimized_goal": optimized_goal.text,  # SMART 원칙이 적용된 목표
            "optimized_response": optimized_response,  # 응답 형식 및 평가 기준
        }

    # _decompose_query 메서드: 2단계 - 쿼리 분해 노드
    # 최적화된 목표를 3~5개의 태스크로 분해하고, 각 태스크마다 2~3개의 옵션 생성
    # 매개변수: state - 현재 상태 (optimized_goal 필드 사용)
    # 반환값: State 업데이트용 딕셔너리 (tasks)
    def _decompose_query(self, state: MultiPathPlanGenerationState) -> dict[str, Any]:
        logger.info("[MultiPathPlanGeneration] 2단계: 쿼리 분해 시작")

        # QueryDecomposer 실행: 목표 → DecomposedTasks (Task 리스트, 각 Task는 여러 옵션 포함)
        tasks = self.query_decomposer.run(query=state.optimized_goal)
        logger.info(f"[MultiPathPlanGeneration] 쿼리 분해 완료 - {len(tasks.values)}개 태스크 생성")

        # State 업데이트: 분해된 태스크들을 State에 저장
        return {"tasks": tasks}  # DecomposedTasks 객체

    # _present_options 메서드: 3단계 - 옵션 제시 노드 (반복)
    # 현재 태스크의 옵션들을 제시하고 LLM이 최적의 옵션을 선택
    # 매개변수: state - 현재 상태 (tasks, current_task_index 필드 사용)
    # 반환값: State 업데이트용 딕셔너리 (chosen_options)
    def _present_options(self, state: MultiPathPlanGenerationState) -> dict[str, Any]:
        # 현재 인덱스의 태스크 가져오기
        current_task = state.tasks.values[state.current_task_index]
        logger.info(f"[MultiPathPlanGeneration] 3단계: 옵션 제시 - 태스크 {state.current_task_index + 1}/{len(state.tasks.values)}")

        # OptionPresenter 실행: 옵션 제시 및 선택 (반환값은 선택된 옵션의 인덱스)
        chosen_option = self.option_presenter.run(task=current_task)

        # State 업데이트: 선택된 옵션 인덱스를 리스트에 추가
        # Annotated[list[int], operator.add]이므로 [chosen_option]을 반환하면 기존 리스트에 추가됨
        return {"chosen_options": [chosen_option]}  # 리스트로 감싸서 반환 (operator.add 때문)

    # _execute_task 메서드: 4단계 - 태스크 실행 노드 (반복)
    # 선택된 옵션에 따라 현재 태스크를 실행하고 결과 저장
    # 매개변수: state - 현재 상태 (tasks, current_task_index, chosen_options 필드 사용)
    # 반환값: State 업데이트용 딕셔너리 (results, current_task_index)
    def _execute_task(self, state: MultiPathPlanGenerationState) -> dict[str, Any]:
        # 현재 태스크와 선택된 옵션 가져오기
        current_task = state.tasks.values[state.current_task_index]
        # chosen_options[-1]: 가장 최근에 선택된 옵션 (현재 태스크의 선택)
        chosen_option = current_task.options[state.chosen_options[-1]]

        logger.info(f"[MultiPathPlanGeneration] 4단계: 태스크 실행 - 태스크 {state.current_task_index + 1}/{len(state.tasks.values)}")

        # TaskExecutor 실행: 태스크와 선택된 옵션으로 실제 작업 수행 (ReAct 에이전트 사용)
        result = self.task_executor.run(
            task=current_task,
            chosen_option=chosen_option,
        )

        logger.info(f"[MultiPathPlanGeneration] 태스크 실행 완료 - {state.current_task_index + 1}/{len(state.tasks.values)}")

        # State 업데이트:
        # 1. results: 실행 결과를 리스트에 추가 (Annotated[list[str], operator.add])
        # 2. current_task_index: 다음 태스크로 인덱스 증가
        return {
            "results": [result],  # 리스트로 감싸서 반환 (operator.add 때문)
            "current_task_index": state.current_task_index + 1,  # 인덱스 증가
        }

    # _aggregate_results 메서드: 5단계 - 결과 집계 노드
    # 모든 태스크의 결과를 종합하여 최종 응답 생성
    # 매개변수: state - 현재 상태 (모든 필드 사용)
    # 반환값: State 업데이트용 딕셔너리 (final_output)
    def _aggregate_results(self, state: MultiPathPlanGenerationState) -> dict[str, Any]:
        logger.info("[MultiPathPlanGeneration] 5단계: 결과 집계 시작")

        # ResultAggregator 실행: 모든 결과를 통합하여 응답 형식에 맞게 재구성
        final_output = self.result_aggregator.run(
            query=state.optimized_goal,  # 최적화된 목표
            response_definition=state.optimized_response,  # 응답 형식 정의
            tasks=state.tasks.values,  # 모든 Task 객체
            chosen_options=state.chosen_options,  # 선택된 옵션들의 인덱스
            results=state.results,  # 모든 태스크의 실행 결과
        )

        logger.info("[MultiPathPlanGeneration] 결과 집계 완료")

        # State 업데이트: 최종 응답을 State에 저장
        return {"final_output": final_output}  # 최종 통합 응답

    # run 메서드: 전체 워크플로우를 실행하는 메인 메서드
    # 매개변수: query - 사용자가 입력한 원본 쿼리 (예: "AI agent 만들기 실습")
    # 반환값: 최종 통합 응답 (문자열)
    def run(self, query: str) -> str:
        # 실행 시작 로그 (구분선으로 가시성 향상)
        logger.info("=" * 80)
        logger.info("[MultiPathPlanGeneration] Multi-Path Plan Generation 시작")
        logger.info(f"[MultiPathPlanGeneration] 입력 쿼리: {query}")
        logger.info("=" * 80)

        # 초기 State 생성: query 필드만 설정, 나머지는 기본값
        initial_state = MultiPathPlanGenerationState(query=query)

        # 그래프 실행: 5단계 워크플로우 자동 실행
        # - initial_state: 시작 상태
        # - recursion_limit: 최대 재귀 깊이 (조건부 엣지의 무한 루프 방지)
        #   태스크가 많거나 복잡한 경우를 대비하여 1000으로 설정
        final_state = self.graph.invoke(initial_state, {"recursion_limit": 1000})

        # 최종 결과 추출: final_output 필드에서 최종 응답 가져오기
        # get 메서드 사용으로 키가 없을 경우 기본값 반환
        final_output = final_state.get("final_output", "최종 답변 생성에 실패했습니다.")

        # 실행 완료 로그
        logger.info("=" * 80)
        logger.info("[MultiPathPlanGeneration] Multi-Path Plan Generation 완료")
        logger.info("=" * 80)

        return final_output  # 최종 통합 응답 반환


# main 함수: CLI에서 프로그램을 실행하는 진입점
def main():
    import argparse  # 명령줄 인자 파싱을 위한 모듈

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler()],
    )

    from settings import Settings  # 설정 파일에서 API 키 및 모델 정보 로드

    # Settings 인스턴스 생성: .env 파일에서 환경 변수 로드
    # - OPENAI_API_KEY: OpenAI API 키
    # - TAVILY_API_KEY: Tavily 검색 API 키
    # - openai_smart_model: 사용할 모델 이름 (예: "gpt-4")
    # - temperature: LLM의 창의성 조절 (0 = 일관성, 1 = 창의성)
    settings = Settings()

    # ArgumentParser 생성: 명령줄 인자 처리
    parser = argparse.ArgumentParser(
        description="MultiPathPlanGeneration을 사용하여 태스크를 실행합니다"
    )
    # --task 인자 추가: 실행할 태스크 (필수)
    # 사용 예: python -m multi_path_plan_generation.main --task "AI agent 만들기 실습"
    parser.add_argument("--task", type=str, required=True, help="실행할 태스크")
    args = parser.parse_args()  # 명령줄 인자 파싱

    # 프로그램 시작 로그 (로깅 설정이 없으면 콘솔에 출력됨)
    logger.info("프로그램 시작")
    logger.info(f"모델: {settings.openai_smart_model}, 온도: {settings.temperature}")

    # LLM 초기화
    # - model: 사용할 모델 (예: "gpt-4", "gpt-3.5-turbo")
    # - temperature: 창의성 조절 (0 = 일관성, 1 = 창의성)
    llm = ChatOpenAI(
        model=settings.openai_smart_model, temperature=settings.temperature
    )

    # MultiPathPlanGeneration 인스턴스 생성
    # - 생성자에서 모든 컴포넌트 초기화 및 워크플로우 그래프 구성
    agent = MultiPathPlanGeneration(llm=llm)

    # 워크플로우 실행: 사용자 쿼리를 처리하여 최종 응답 생성
    # 내부적으로 5단계 워크플로우가 자동으로 실행됨:
    # 1. 목표 설정 → 2. 쿼리 분해 → 3. 옵션 제시 (반복) → 4. 태스크 실행 (반복) → 5. 결과 집계
    result = agent.run(query=args.task)

    # 최종 결과 출력 (사용자에게 표시)
    print("\n=== 최종 출력 ===")
    print(result)

    # 프로그램 종료 로그
    logger.info("프로그램 종료")


# 스크립트가 직접 실행될 때만 main 함수 호출
# 다른 모듈에서 import될 때는 실행되지 않음
if __name__ == "__main__":
    main()
