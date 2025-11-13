"""
요구사항 정의서 생성 AI 에이전트 (Documentation Agent)

이 모듈은 LangGraph를 사용하여 사용자 요청을 기반으로 다양한 페르소나를 생성하고,
각 페르소나와 인터뷰를 진행한 후, 수집된 정보를 바탕으로 포괄적인 요구사항 문서를
자동으로 생성하는 AI 에이전트를 구현합니다.

주요 구성 요소:
1. PersonaGenerator: 다양한 사용자 페르소나 생성
2. InterviewConductor: 각 페르소나와 인터뷰 수행
3. InformationEvaluator: 수집된 정보의 충분성 평가
4. RequirementsDocumentGenerator: 최종 요구사항 문서 생성
5. DocumentationAgent: 전체 프로세스를 조율하는 LangGraph 기반 에이전트

참조 문서:
- LangGraph StateGraph: https://docs.langchain.com/oss/python/langgraph/graph-api
- ChatOpenAI with_structured_output: https://python.langchain.com/api_reference/openai/chat_models/
- Pydantic BaseModel: https://docs.pydantic.dev/latest/concepts/models/
"""

import operator  # Python 표준 라이브러리: 연산자를 함수로 제공 (여기서는 add 연산자를 사용)
from typing import Annotated, Any, Optional  # 타입 힌팅을 위한 모듈

# dotenv: .env 파일에서 환경 변수를 로드하는 라이브러리
# OpenAI API 키 등 민감한 정보를 안전하게 관리하기 위해 사용
from dotenv import load_dotenv

# LangChain Core 모듈
# StrOutputParser: LLM의 출력을 문자열로 파싱하는 파서
from langchain_core.output_parsers import StrOutputParser

# ChatPromptTemplate: 대화형 프롬프트를 생성하는 템플릿 클래스
# 시스템 메시지와 사용자 메시지를 구조화하여 LLM에 전달
from langchain_core.prompts import ChatPromptTemplate

# ChatOpenAI: OpenAI의 Chat 모델(GPT-4, GPT-3.5 등)을 LangChain에서 사용하기 위한 래퍼 클래스
from langchain_openai import ChatOpenAI

# LangGraph: 상태 기반 그래프로 AI 에이전트 워크플로우를 구현하는 프레임워크
# StateGraph: 상태를 중심으로 노드와 엣지를 정의하여 그래프를 구성하는 클래스
# END: 그래프의 종료 지점을 나타내는 특수 상수
from langgraph.graph import END, StateGraph

# Pydantic: Python 데이터 검증 및 설정 관리 라이브러리
# BaseModel: 데이터 모델의 기본 클래스 (타입 검증, 직렬화/역직렬화 등 제공)
# Field: 모델 필드의 메타데이터(기본값, 설명, 제약조건 등)를 정의하는 함수
from pydantic import BaseModel, Field

# .env 파일에서 환경 변수 불러오기
# 프로젝트 루트의 .env 파일에서 OPENAI_API_KEY 등의 환경 변수를 자동으로 로드
load_dotenv()


# ============================================================================
# 데이터 모델 정의 (Pydantic BaseModel)
# ============================================================================
# Pydantic은 타입 힌트를 기반으로 데이터 검증과 직렬화를 자동으로 수행합니다.
# LangChain의 with_structured_output()과 함께 사용하면 LLM이 구조화된
# 데이터를 반환하도록 강제할 수 있습니다.
# 참조: https://docs.pydantic.dev/latest/concepts/models/


class Persona(BaseModel):
    """
    개별 페르소나를 표현하는 데이터 모델

    페르소나는 가상의 사용자 프로필로, 다양한 관점에서 요구사항을 수집하기 위해 사용됩니다.
    각 페르소나는 특정 사용자 그룹의 특성, 니즈, 목표를 대표합니다.

    Attributes:
        name (str): 페르소나의 이름 (예: "김철수", "이영희")
        background (str): 페르소나의 배경 정보 (나이, 직업, 기술 수준, 목표 등)

    Example:
        >>> persona = Persona(
        ...     name="김철수",
        ...     background="35세 직장인, IT 전문가, 업무 자동화에 관심"
        ... )
    """
    name: str = Field(..., description="페르소나의 이름")
    background: str = Field(..., description="페르소나의 배경")


class Personas(BaseModel):
    """
    페르소나 목록을 담는 컨테이너 모델

    LLM의 with_structured_output()을 통해 여러 개의 페르소나를 한 번에 생성할 때 사용됩니다.

    Attributes:
        personas (list[Persona]): Persona 객체들의 리스트
    """
    personas: list[Persona] = Field(
        default_factory=list, description="페르소나 목록"
    )


class Interview(BaseModel):
    """
    개별 인터뷰 내용을 표현하는 데이터 모델

    각 페르소나에게 특정 질문을 하고 받은 답변을 저장합니다.

    Attributes:
        persona (Persona): 인터뷰 대상 페르소나
        question (str): 페르소나에게 한 질문
        answer (str): 페르소나로부터 받은 답변
    """
    persona: Persona = Field(..., description="인터뷰 대상 페르소나")
    question: str = Field(..., description="인터뷰 질문")
    answer: str = Field(..., description="인터뷰 답변")


class InterviewResult(BaseModel):
    """
    여러 인터뷰 결과를 담는 컨테이너 모델

    한 번의 인터뷰 세션에서 여러 페르소나와 진행한 인터뷰들을 모아 관리합니다.

    Attributes:
        interviews (list[Interview]): Interview 객체들의 리스트
    """
    interviews: list[Interview] = Field(
        default_factory=list, description="인터뷰 결과 목록"
    )


class EvaluationResult(BaseModel):
    """
    정보 충분성 평가 결과를 표현하는 데이터 모델

    현재까지 수집한 인터뷰 정보가 요구사항 문서 작성에 충분한지 판단합니다.
    LLM이 구조화된 형태로 평가 결과를 반환하도록 합니다.

    Attributes:
        reason (str): 충분하다/부족하다고 판단한 이유
        is_sufficient (bool): 정보가 충분한지 여부 (True: 충분, False: 부족)
    """
    reason: str = Field(..., description="판단 이유")
    is_sufficient: bool = Field(..., description="정보가 충분한지 여부")


class InterviewState(BaseModel):
    """
    LangGraph 워크플로우의 전체 상태를 관리하는 모델

    LangGraph의 StateGraph는 상태를 중심으로 동작합니다. 각 노드는 이 상태를
    읽고 수정하며, 그래프를 통해 상태가 순차적으로 업데이트됩니다.

    Annotated[list[Persona], operator.add] 설명:
    - Annotated: Python 3.9+의 타입 힌트 확장 문법
    - operator.add: LangGraph에서 리스트 필드를 누적(accumulate)하는 방식을 지정
    - 기본적으로 LangGraph는 상태 업데이트 시 필드를 덮어쓰지만,
      operator.add를 지정하면 기존 리스트에 새 항목을 추가(extend)합니다.
    - 예: state.personas = [A, B] → 노드가 [C]를 반환 → state.personas = [A, B, C]

    참조: https://docs.langchain.com/oss/python/langgraph/graph-api

    Attributes:
        user_request (str): 사용자의 초기 요청 (예: "건강 관리 앱을 개발하고 싶다")
        personas (list[Persona]): 생성된 모든 페르소나들 (operator.add로 누적)
        interviews (list[Interview]): 수행된 모든 인터뷰들 (operator.add로 누적)
        requirements_doc (str): 최종 생성된 요구사항 문서
        iteration (int): 현재까지 페르소나 생성 및 인터뷰를 반복한 횟수
        is_information_sufficient (bool): 정보 수집이 충분한지 여부
    """
    user_request: str = Field(..., description="사용자 요청")
    personas: Annotated[list[Persona], operator.add] = Field(
        default_factory=list, description="생성된 페르소나 목록"
    )
    interviews: Annotated[list[Interview], operator.add] = Field(
        default_factory=list, description="실시된 인터뷰 목록"
    )
    requirements_doc: str = Field(default="", description="생성된 요구사항 정의")
    iteration: int = Field(
        default=0, description="페르소나 생성과 인터뷰의 반복 횟수"
    )
    is_information_sufficient: bool = Field(
        default=False, description="정보가 충분한지 여부"
    )


# ============================================================================
# PersonaGenerator: 다양한 페르소나 생성
# ============================================================================


class PersonaGenerator:
    """
    사용자 요청을 분석하여 다양한 페르소나를 생성하는 클래스

    이 클래스는 LLM을 사용하여 사용자의 요청에 관련된 여러 유형의 사용자 페르소나를
    자동으로 생성합니다. 다양한 관점(나이, 성별, 직업, 기술 수준 등)을 가진
    페르소나를 생성하여 포괄적인 요구사항 수집을 가능하게 합니다.

    Attributes:
        llm (ChatOpenAI): 구조화된 출력을 생성하도록 설정된 LLM 인스턴스
        k (int): 생성할 페르소나의 개수

    Methods:
        run(user_request: str) -> Personas: 사용자 요청을 기반으로 페르소나 생성
    """

    def __init__(self, llm: ChatOpenAI, k: int = 5):
        """
        PersonaGenerator 초기화

        Args:
            llm (ChatOpenAI): OpenAI Chat 모델 인스턴스
            k (int, optional): 생성할 페르소나 수. 기본값은 5.

        Note:
            with_structured_output(Personas):
            - LangChain의 구조화된 출력 기능을 사용
            - LLM이 자유 형식 텍스트 대신 Personas 모델 형태로 응답하도록 강제
            - Pydantic 모델의 스키마를 LLM에 전달하여 JSON 형식 응답 유도
            - 참조: https://python.langchain.com/api_reference/openai/chat_models/
        """
        self.llm = llm.with_structured_output(Personas)
        self.k = k

    def run(self, user_request: str) -> Personas:
        """
        사용자 요청을 기반으로 다양한 페르소나 생성

        Args:
            user_request (str): 사용자의 애플리케이션 개발 요청
                              예: "스마트폰용 건강 관리 앱을 개발하고 싶다"

        Returns:
            Personas: 생성된 페르소나 목록을 담은 Personas 객체

        Process:
            1. 프롬프트 템플릿 생성 (시스템 메시지 + 사용자 메시지)
            2. LangChain의 LCEL(LangChain Expression Language)을 사용한 체인 구성
            3. 체인 실행으로 구조화된 페르소나 생성
        """
        # ChatPromptTemplate: 대화형 프롬프트를 구조화
        # from_messages()는 (role, content) 튜플 리스트를 받아 프롬프트 생성
        # 참조: https://python.langchain.com/api_reference/core/prompts/
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",  # 시스템 메시지: LLM의 역할과 행동 방식 정의
                    "당신은 사용자 인터뷰용 다양한 페르소나를 만드는 전문가입니다.",
                ),
                (
                    "human",  # 사용자 메시지: 구체적인 작업 지시
                    f"다음 사용자 요청에 관한 인터뷰를 위해 {self.k}명의 다양한 페르소나를 생성해주세요.\n\n"
                    "사용자 요청: {user_request}\n\n"
                    "각 페르소나에는 이름과 간단한 배경을 포함해주세요. 나이, 성별, 직업, 기술적 전문 지식에서 다양성을 확보해 주세요.",
                ),
            ]
        )
        # LCEL을 사용한 체인 구성: prompt | llm
        # | 연산자는 Runnable 객체들을 순차적으로 연결
        # prompt의 출력이 llm의 입력으로 자동 전달됨
        chain = prompt | self.llm

        # invoke(): 체인을 동기적으로 실행
        # 입력 딕셔너리의 키(user_request)가 프롬프트 템플릿의 변수와 매칭됨
        return chain.invoke({"user_request": user_request})


# ============================================================================
# InterviewConductor: 페르소나 인터뷰 진행
# ============================================================================


class InterviewConductor:
    """
    각 페르소나와 인터뷰를 수행하는 클래스

    이 클래스는 생성된 페르소나들에게 적절한 질문을 생성하고,
    각 페르소나의 관점에서 답변을 얻어 인터뷰를 완성합니다.

    Process:
        1. 각 페르소나에 맞는 질문 생성
        2. 각 페르소나의 관점에서 답변 생성
        3. 질문-답변 쌍을 Interview 객체로 구조화

    Attributes:
        llm (ChatOpenAI): LLM 인스턴스 (질문 및 답변 생성에 사용)

    Methods:
        run(user_request, personas): 전체 인터뷰 프로세스 실행
        _generate_questions(): 페르소나별 질문 생성
        _generate_answers(): 페르소나별 답변 생성
        _create_interviews(): Interview 객체 생성
    """

    def __init__(self, llm: ChatOpenAI):
        """
        InterviewConductor 초기화

        Args:
            llm (ChatOpenAI): OpenAI Chat 모델 인스턴스
                            (여기서는 with_structured_output을 사용하지 않음)
        """
        self.llm = llm

    def run(self, user_request: str, personas: list[Persona]) -> InterviewResult:
        """
        전체 인터뷰 프로세스 실행

        Args:
            user_request (str): 사용자의 원본 요청
            personas (list[Persona]): 인터뷰 대상 페르소나 리스트

        Returns:
            InterviewResult: 완성된 인터뷰 결과 목록

        Note:
            이 메서드는 3단계 프로세스를 순차적으로 실행합니다.
            질문 생성 → 답변 생성 → 인터뷰 객체 생성
        """
        # 1단계: 각 페르소나에 맞는 질문 생성
        questions = self._generate_questions(
            user_request=user_request, personas=personas
        )

        # 2단계: 각 페르소나의 관점에서 답변 생성
        answers = self._generate_answers(personas=personas, questions=questions)

        # 3단계: 질문-답변 쌍을 Interview 객체로 변환
        interviews = self._create_interviews(
            personas=personas, questions=questions, answers=answers
        )

        # InterviewResult 객체로 래핑하여 반환
        return InterviewResult(interviews=interviews)

    def _generate_questions(
        self, user_request: str, personas: list[Persona]
    ) -> list[str]:
        """
        각 페르소나에 맞춤화된 질문 생성

        각 페르소나의 배경과 특성을 고려하여 해당 페르소나에게
        가장 적절한 질문을 LLM을 통해 생성합니다.

        Args:
            user_request (str): 사용자의 원본 요청
            personas (list[Persona]): 질문을 생성할 페르소나 리스트

        Returns:
            list[str]: 페르소나별 질문 리스트 (순서 유지)

        Note:
            batch() 메서드를 사용하여 여러 질문을 병렬로 생성함으로써
            API 호출 횟수를 줄이고 성능을 최적화합니다.
        """
        # 질문 생성용 프롬프트 템플릿 정의
        question_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "당신은 사용자 요구사항에 기반하여 적절한 질문을 생성하는 전문가입니다.",
                ),
                (
                    "human",
                    "다음 페르소나와 관련된 사용자 요청에 대해 한 가지 질문을 생성해 주세요.\n\n"
                    "사용자 요청: {user_request}\n"
                    "페르소나: {persona_name} - {persona_background}\n\n"
                    "질문은 구체적이고, 이 페르소나의 관점에서 중요한 정보를 이끌어낼 수 있도록 설계해 주세요.",
                ),
            ]
        )

        # 체인 구성: prompt → llm → string parser
        # StrOutputParser()는 LLM의 AIMessage를 문자열로 변환
        question_chain = question_prompt | self.llm | StrOutputParser()

        # 각 페르소나에 대한 입력 데이터 준비 (리스트 컴프리헨션)
        question_queries = [
            {
                "user_request": user_request,
                "persona_name": persona.name,
                "persona_background": persona.background,
            }
            for persona in personas
        ]

        # batch(): 여러 입력을 한 번에 처리 (병렬 처리로 성능 향상)
        # 예: personas가 5개면 5개의 질문을 병렬로 생성
        return question_chain.batch(question_queries)

    def _generate_answers(
        self, personas: list[Persona], questions: list[str]
    ) -> list[str]:
        """
        각 페르소나의 관점에서 답변 생성

        LLM에게 특정 페르소나의 역할을 부여하고, 그 페르소나의
        관점에서 질문에 답하도록 합니다 (Role-playing).

        Args:
            personas (list[Persona]): 답변할 페르소나 리스트
            questions (list[str]): 각 페르소나에 대한 질문 리스트

        Returns:
            list[str]: 페르소나별 답변 리스트 (순서 유지)

        Note:
            시스템 메시지에 페르소나 정보를 포함시켜 LLM이 해당
            페르소나의 관점에서 답변하도록 유도합니다.
        """
        # 답변 생성용 프롬프트 템플릿 정의
        answer_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    # 시스템 메시지에서 LLM의 역할(페르소나)을 명확히 지정
                    "당신은 다음 페르소나로서 답변하고 있습니다: {persona_name} - {persona_background}",
                ),
                (
                    "human",
                    "질문: {question}"
                ),
            ]
        )

        # 체인 구성: prompt → llm → string parser
        answer_chain = answer_prompt | self.llm | StrOutputParser()

        # 각 페르소나-질문 쌍에 대한 입력 데이터 준비
        # zip()을 사용하여 페르소나와 질문을 쌍으로 매칭
        answer_queries = [
            {
                "persona_name": persona.name,
                "persona_background": persona.background,
                "question": question,
            }
            for persona, question in zip(personas, questions)
        ]

        # batch(): 모든 답변을 병렬로 생성
        return answer_chain.batch(answer_queries)

    def _create_interviews(
        self, personas: list[Persona], questions: list[str], answers: list[str]
    ) -> list[Interview]:
        """
        페르소나, 질문, 답변을 Interview 객체로 결합

        세 개의 리스트(personas, questions, answers)를 zip으로 묶어
        각 세트를 Interview 객체로 변환합니다.

        Args:
            personas (list[Persona]): 페르소나 리스트
            questions (list[str]): 질문 리스트
            answers (list[str]): 답변 리스트

        Returns:
            list[Interview]: 완성된 Interview 객체 리스트

        Note:
            zip()은 세 리스트의 같은 인덱스 요소들을 튜플로 묶어줍니다.
            예: personas[0], questions[0], answers[0] → Interview 객체
        """
        return [
            Interview(persona=persona, question=question, answer=answer)
            for persona, question, answer in zip(personas, questions, answers)
        ]


# ============================================================================
# InformationEvaluator: 정보 충분성 평가
# ============================================================================


class InformationEvaluator:
    """
    수집된 인터뷰 정보가 요구사항 문서 작성에 충분한지 평가하는 클래스

    LLM을 사용하여 현재까지 수집된 인터뷰 정보를 분석하고,
    요구사항 문서를 작성하기에 충분한 정보가 모였는지 판단합니다.

    Attributes:
        llm (ChatOpenAI): 구조화된 평가 결과를 생성하도록 설정된 LLM

    Methods:
        run(user_request, interviews): 정보 충분성 평가 실행
    """

    def __init__(self, llm: ChatOpenAI):
        """
        InformationEvaluator 초기화

        Args:
            llm (ChatOpenAI): OpenAI Chat 모델 인스턴스

        Note:
            with_structured_output(EvaluationResult)를 사용하여
            LLM이 평가 이유(reason)와 충분성 여부(is_sufficient)를
            구조화된 형태로 반환하도록 설정합니다.
        """
        self.llm = llm.with_structured_output(EvaluationResult)

    def run(self, user_request: str, interviews: list[Interview]) -> EvaluationResult:
        """
        사용자 요청과 인터뷰 결과를 기반으로 정보의 충분성을 평가

        Args:
            user_request (str): 사용자의 원본 요청
            interviews (list[Interview]): 현재까지 수집된 인터뷰 리스트

        Returns:
            EvaluationResult: 평가 이유와 충분성 여부를 담은 객체

        Process:
            1. 모든 인터뷰를 텍스트로 포맷팅
            2. LLM에게 정보 충분성 판단 요청
            3. 구조화된 평가 결과 반환

        Note:
            이 평가 결과는 LangGraph의 조건부 엣지에서 사용되어
            추가 인터뷰를 진행할지, 요구사항 문서를 생성할지 결정합니다.
        """
        # 평가용 프롬프트 템플릿 정의
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "당신은 포괄적인 요구사항 문서를 작성하기 위한 정보의 충분성을 평가하는 전문가입니다.",
                ),
                (
                    "human",
                    "다음 사용자 요청과 인터뷰 결과에 기반하여, 포괄적인 요구사항 문서를 작성하기에 충분한 정보가 모였는지 판단해 주세요.\n\n"
                    "사용자 요청: {user_request}\n\n"
                    "인터뷰 결과:\n{interview_results}",
                ),
            ]
        )

        # 체인 구성: prompt → llm (with_structured_output 적용됨)
        chain = prompt | self.llm

        # 인터뷰 결과를 읽기 쉬운 텍스트 형식으로 변환
        # "\n".join()을 사용하여 각 인터뷰를 줄바꿈으로 구분
        interview_text = "\n".join(
            f"페르소나: {i.persona.name} - {i.persona.background}\n"
            f"질문: {i.question}\n답변: {i.answer}\n"
            for i in interviews
        )

        # 체인 실행 및 구조화된 평가 결과 반환
        return chain.invoke(
            {
                "user_request": user_request,
                "interview_results": interview_text,
            }
        )


# ============================================================================
# RequirementsDocumentGenerator: 최종 요구사항 문서 생성
# ============================================================================


class RequirementsDocumentGenerator:
    """
    수집된 인터뷰 정보를 바탕으로 최종 요구사항 문서를 생성하는 클래스

    모든 페르소나 인터뷰 결과를 종합하여 구조화된 요구사항 문서를 작성합니다.
    문서는 7개의 주요 섹션으로 구성됩니다.

    Document Structure:
        1. 프로젝트 개요
        2. 주요 기능
        3. 비기능 요구사항
        4. 제약 조건
        5. 타겟 사용자
        6. 우선순위
        7. 리스크와 완화 방안

    Attributes:
        llm (ChatOpenAI): LLM 인스턴스 (자유 형식 텍스트 생성)

    Methods:
        run(user_request, interviews): 요구사항 문서 생성 실행
    """

    def __init__(self, llm: ChatOpenAI):
        """
        RequirementsDocumentGenerator 초기화

        Args:
            llm (ChatOpenAI): OpenAI Chat 모델 인스턴스

        Note:
            여기서는 with_structured_output을 사용하지 않습니다.
            자유 형식의 마크다운 문서를 생성하기 때문입니다.
        """
        self.llm = llm

    def run(self, user_request: str, interviews: list[Interview]) -> str:
        """
        사용자 요청과 인터뷰 결과를 바탕으로 요구사항 문서 생성

        Args:
            user_request (str): 사용자의 원본 요청
            interviews (list[Interview]): 수집된 모든 인터뷰 리스트

        Returns:
            str: 마크다운 형식의 완성된 요구사항 문서

        Process:
            1. 모든 인터뷰를 텍스트로 포맷팅
            2. 7가지 섹션을 포함한 문서 생성 지시
            3. LLM이 종합 분석하여 문서 작성
            4. 한국어 마크다운 문서 반환

        Note:
            프롬프트에 명확한 문서 구조를 제시하여
            일관성 있는 형식의 문서를 생성하도록 유도합니다.
        """
        # 문서 생성용 프롬프트 템플릿 정의
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "당신은 수집한 정보를 바탕으로 요구사항 문서를 작성하는 전문가입니다.",
                ),
                (
                    "human",
                    "다음 사용자 요청과 여러 페르소나의 인터뷰 결과에 기반하여, 요구사항 문서를 작성해 주세요.\n\n"
                    "사용자 요청: {user_request}\n\n"
                    "인터뷰 결과:\n{interview_results}\n"
                    "요구사항 문서에는 다음 섹션을 포함해주세요:\n"
                    "1. 프로젝트 개요\n"
                    "2. 주요 기능\n"
                    "3. 비기능 요구사항\n"
                    "4. 제약 조건\n"
                    "5. 타겟 사용자\n"
                    "6. 우선순위\n"
                    "7. 리스크와 완화 방안\n\n"
                    "출력은 반드시 한국어로 부탁드립니다.\n\n요구사항 문서:",
                ),
            ]
        )

        # 체인 구성: prompt → llm → string parser
        # StrOutputParser()로 LLM의 응답을 순수 문자열로 변환
        chain = prompt | self.llm | StrOutputParser()

        # 인터뷰 결과를 읽기 쉬운 텍스트 형식으로 변환
        interview_text = "\n".join(
            f"페르소나: {i.persona.name} - {i.persona.background}\n"
            f"질문: {i.question}\n답변: {i.answer}\n"
            for i in interviews
        )

        # 체인 실행 및 최종 요구사항 문서 반환
        return chain.invoke(
            {
                "user_request": user_request,
                "interview_results": interview_text,
            }
        )


# ============================================================================
# DocumentationAgent: 전체 워크플로우를 조율하는 LangGraph 에이전트
# ============================================================================


class DocumentationAgent:
    """
    요구사항 정의서 생성 AI 에이전트 (메인 클래스)

    LangGraph의 StateGraph를 사용하여 전체 워크플로우를 조율합니다.
    페르소나 생성 → 인터뷰 → 평가를 반복하며, 충분한 정보가 모이면
    최종 요구사항 문서를 생성합니다.

    Workflow Graph Structure:
        [START]
           ↓
        [generate_personas] → 페르소나 생성
           ↓
        [conduct_interviews] → 인터뷰 수행
           ↓
        [evaluate_information] → 정보 충분성 평가
           ↓ (조건부)
        정보 부족 & iteration < 5 → [generate_personas]로 돌아가 반복
        정보 충분 or iteration >= 5 → [generate_requirements]로 진행
           ↓
        [generate_requirements] → 최종 문서 생성
           ↓
        [END]

    참조: https://docs.langchain.com/oss/python/langgraph/graph-api

    Attributes:
        persona_generator (PersonaGenerator): 페르소나 생성기
        interview_conductor (InterviewConductor): 인터뷰 진행자
        information_evaluator (InformationEvaluator): 정보 평가자
        requirements_generator (RequirementsDocumentGenerator): 문서 생성기
        graph (CompiledGraph): 컴파일된 LangGraph 워크플로우

    Methods:
        run(user_request): 전체 워크플로우 실행
        _create_graph(): LangGraph 워크플로우 생성
        _generate_personas(state): 페르소나 생성 노드
        _conduct_interviews(state): 인터뷰 수행 노드
        _evaluate_information(state): 정보 평가 노드
        _generate_requirements(state): 문서 생성 노드
    """

    def __init__(self, llm: ChatOpenAI, k: Optional[int] = None):
        """
        DocumentationAgent 초기화

        Args:
            llm (ChatOpenAI): OpenAI Chat 모델 인스턴스
            k (Optional[int]): 생성할 페르소나 수 (기본값: 5)
        """
        # 각 단계별 컴포넌트 초기화
        self.persona_generator = PersonaGenerator(llm=llm, k=k)
        self.interview_conductor = InterviewConductor(llm=llm)
        self.information_evaluator = InformationEvaluator(llm=llm)
        self.requirements_generator = RequirementsDocumentGenerator(llm=llm)

        # LangGraph 워크플로우 그래프 생성 및 컴파일
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        """
        LangGraph 워크플로우 생성 및 컴파일

        Returns:
            CompiledGraph: 실행 가능한 컴파일된 그래프

        Graph Components:
            - Nodes: 각 단계의 작업을 수행하는 함수
            - Edges: 노드 간의 연결 (일반 엣지와 조건부 엣지)
            - Entry Point: 그래프의 시작 노드
            - END: 그래프의 종료 지점

        Note:
            compile() 메서드를 호출해야 실행 가능한 그래프가 됩니다.
            컴파일 전의 StateGraph는 빌더 패턴의 설정 객체입니다.
        """
        # StateGraph 초기화: InterviewState를 상태 스키마로 사용
        workflow = StateGraph(InterviewState)

        # 노드 추가: (노드명, 실행할 함수)
        # 각 노드 함수는 state를 받아 dict를 반환하며,
        # 반환된 dict가 state에 병합됩니다.
        workflow.add_node("generate_personas", self._generate_personas)
        workflow.add_node("conduct_interviews", self._conduct_interviews)
        workflow.add_node("evaluate_information", self._evaluate_information)
        workflow.add_node("generate_requirements", self._generate_requirements)

        # 시작 노드 설정: 그래프 실행 시 가장 먼저 실행될 노드
        workflow.set_entry_point("generate_personas")

        # 일반 엣지 추가: 무조건 다음 노드로 이동
        workflow.add_edge("generate_personas", "conduct_interviews")
        workflow.add_edge("conduct_interviews", "evaluate_information")

        # 조건부 엣지 추가: 상태에 따라 다음 노드 결정
        # add_conditional_edges(source, condition_func, edge_map)
        # - source: 조건을 평가할 시작 노드
        # - condition_func: 상태를 받아 True/False를 반환하는 함수
        # - edge_map: {condition_result: next_node} 매핑
        workflow.add_conditional_edges(
            "evaluate_information",
            # 조건: 정보가 부족하고 반복 횟수가 5 미만
            lambda state: not state.is_information_sufficient and state.iteration < 5,
            {
                True: "generate_personas",  # 정보 부족 → 다시 페르소나 생성
                False: "generate_requirements",  # 정보 충분 → 문서 생성
            },
        )

        # 문서 생성 후 그래프 종료
        workflow.add_edge("generate_requirements", END)

        # 그래프 컴파일: 실행 가능한 형태로 변환
        return workflow.compile()

    def _generate_personas(self, state: InterviewState) -> dict[str, Any]:
        """
        페르소나 생성 노드

        현재 상태의 user_request를 기반으로 새로운 페르소나를 생성합니다.

        Args:
            state (InterviewState): 현재 워크플로우 상태

        Returns:
            dict[str, Any]: 상태에 병합될 업데이트
                - personas: 새로 생성된 페르소나 리스트 (operator.add로 누적)
                - iteration: 증가된 반복 횟수

        Note:
            personas 필드는 Annotated[list[Persona], operator.add]로 정의되어
            있으므로, 반환된 리스트가 기존 리스트에 추가(extend)됩니다.
        """
        # PersonaGenerator를 사용하여 페르소나 생성
        new_personas: Personas = self.persona_generator.run(state.user_request)

        # 상태 업데이트 딕셔너리 반환
        return {
            "personas": new_personas.personas,  # operator.add로 기존 리스트에 추가
            "iteration": state.iteration + 1,  # 반복 횟수 증가
        }

    def _conduct_interviews(self, state: InterviewState) -> dict[str, Any]:
        """
        인터뷰 수행 노드

        최근 생성된 페르소나들과 인터뷰를 진행합니다.

        Args:
            state (InterviewState): 현재 워크플로우 상태

        Returns:
            dict[str, Any]: 상태에 병합될 업데이트
                - interviews: 새로 수행된 인터뷰 리스트 (operator.add로 누적)

        Note:
            state.personas[-5:]는 최근 5개의 페르소나만 선택합니다.
            이는 매 반복마다 새로 생성된 페르소나들과만 인터뷰하기 위함입니다.
        """
        # InterviewConductor를 사용하여 인터뷰 수행
        # 최근 5개 페르소나만 선택 (k=5가 기본값이므로)
        new_interviews: InterviewResult = self.interview_conductor.run(
            state.user_request, state.personas[-5:]
        )

        # 상태 업데이트 딕셔너리 반환
        return {"interviews": new_interviews.interviews}  # operator.add로 기존 리스트에 추가

    def _evaluate_information(self, state: InterviewState) -> dict[str, Any]:
        """
        정보 충분성 평가 노드

        현재까지 수집된 모든 인터뷰 정보가 요구사항 문서 작성에
        충분한지 LLM을 통해 평가합니다.

        Args:
            state (InterviewState): 현재 워크플로우 상태

        Returns:
            dict[str, Any]: 상태에 병합될 업데이트
                - is_information_sufficient: 정보 충분성 여부
                - evaluation_reason: 평가 이유

        Note:
            이 평가 결과는 조건부 엣지에서 사용되어 워크플로우의
            다음 단계(반복 or 문서 생성)를 결정합니다.
        """
        # InformationEvaluator를 사용하여 정보 충분성 평가
        evaluation_result: EvaluationResult = self.information_evaluator.run(
            state.user_request, state.interviews
        )

        # 상태 업데이트 딕셔너리 반환
        return {
            "is_information_sufficient": evaluation_result.is_sufficient,
            "evaluation_reason": evaluation_result.reason,
        }

    def _generate_requirements(self, state: InterviewState) -> dict[str, Any]:
        """
        요구사항 문서 생성 노드

        수집된 모든 인터뷰 정보를 바탕으로 최종 요구사항 문서를 생성합니다.

        Args:
            state (InterviewState): 현재 워크플로우 상태

        Returns:
            dict[str, Any]: 상태에 병합될 업데이트
                - requirements_doc: 생성된 최종 요구사항 문서

        Note:
            이 노드는 워크플로우의 마지막 단계이며,
            이 노드 실행 후 그래프는 END로 종료됩니다.
        """
        # RequirementsDocumentGenerator를 사용하여 문서 생성
        requirements_doc: str = self.requirements_generator.run(
            state.user_request, state.interviews
        )

        # 상태 업데이트 딕셔너리 반환
        return {"requirements_doc": requirements_doc}

    def run(self, user_request: str) -> str:
        """
        전체 워크플로우 실행

        사용자 요청을 입력받아 전체 프로세스를 실행하고
        최종 요구사항 문서를 반환합니다.

        Args:
            user_request (str): 사용자의 애플리케이션 개발 요청

        Returns:
            str: 생성된 최종 요구사항 문서

        Process:
            1. 초기 상태 생성
            2. 그래프 실행 (invoke)
            3. 최종 상태에서 requirements_doc 추출
            4. 문서 반환

        Note:
            graph.invoke()는 동기적으로 전체 그래프를 실행합니다.
            비동기 실행을 원하면 graph.ainvoke()를 사용할 수 있습니다.
        """
        # 초기 상태 객체 생성 (user_request만 설정)
        initial_state = InterviewState(user_request=user_request)

        # 그래프 실행: 초기 상태를 입력으로 전달
        # invoke()는 그래프를 처음부터 끝까지 실행하고 최종 상태를 반환
        final_state = self.graph.invoke(initial_state)

        # 최종 상태에서 생성된 요구사항 문서 추출 및 반환
        return final_state["requirements_doc"]


# ============================================================================
# 메인 실행 함수 (CLI 인터페이스)
# ============================================================================


def main():
    """
    커맨드 라인 인터페이스를 통한 에이전트 실행

    사용자로부터 커맨드 라인 인자를 받아 DocumentationAgent를 실행하고
    최종 요구사항 문서를 출력합니다.

    Command Line Arguments:
        --task (str): 개발하고 싶은 애플리케이션에 대한 설명 (필수)
        --k (int): 생성할 페르소나 수 (기본값: 5)

    Usage:
        # 기본 사용법
        python -m documentation_agent.main --task "스마트폰용 건강 관리 앱을 개발하고 싶다"

        # 페르소나 수 지정
        python -m documentation_agent.main --task "온라인 쇼핑몰을 개발하고 싶다" --k 3

        # Poetry를 사용하는 경우
        poetry run python -m documentation_agent.main --task "여기에 요청을 입력하세요"

    Environment Variables (Required):
        OPENAI_API_KEY: OpenAI API 인증 키
        LANGCHAIN_API_KEY: LangChain (LangSmith) API 인증 키 (선택사항)

    Note:
        .env 파일에 환경 변수가 설정되어 있어야 합니다.
        load_dotenv()가 파일 시작 부분에서 이미 호출되었습니다.
    """
    import argparse

    # argparse: Python 표준 라이브러리의 커맨드 라인 인자 파싱 모듈
    # ArgumentParser: 인자 정의 및 파싱을 관리하는 클래스
    parser = argparse.ArgumentParser(
        description="사용자 요구에 기반하여 요구사항 정의를 생성합니다"
    )

    # --task 인자 정의: 사용자의 애플리케이션 개발 요청
    parser.add_argument(
        "--task",
        type=str,
        help="개발하고 싶은 애플리케이션에 대해 기술해 주세요",
    )

    # --k 인자 정의: 생성할 페르소나 수
    parser.add_argument(
        "--k",
        type=int,
        default=5,  # 기본값: 5명의 페르소나
        help="생성할 페르소나 수를 설정하세요(기본값: 5)",
    )

    # 커맨드 라인 인자 파싱
    # parse_args()는 sys.argv를 파싱하여 Namespace 객체 반환
    args = parser.parse_args()

    # ChatOpenAI 모델 초기화
    # - model: 사용할 OpenAI 모델 (gpt-4o는 최신 GPT-4 Optimized 모델)
    # - temperature: 생성 다양성 제어 (0.0 = 가장 결정론적, 1.0 = 가장 다양)
    #   요구사항 문서는 일관성이 중요하므로 0.0으로 설정
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0)

    # DocumentationAgent 초기화
    # - llm: 모든 LLM 작업에 사용될 모델 인스턴스
    # - k: 생성할 페르소나 수 (커맨드 라인 인자로 전달)
    agent = DocumentationAgent(llm=llm, k=args.k)

    # 에이전트 실행
    # - user_request: 사용자가 --task로 전달한 요청
    # - 반환값: 최종 생성된 요구사항 문서 (문자열)
    # 내부적으로 LangGraph 워크플로우가 실행됨:
    #   페르소나 생성 → 인터뷰 → 평가 → (반복 or 문서 생성)
    final_output = agent.run(user_request=args.task)

    # 최종 생성된 요구사항 문서를 표준 출력으로 출력
    # 이 출력은 마크다운 형식의 구조화된 문서입니다
    print(final_output)


# Python 모듈 실행 시 자동으로 main() 함수 호출
# 이 블록은 모듈이 직접 실행될 때만 실행되고,
# import될 때는 실행되지 않습니다.
if __name__ == "__main__":
    main()
