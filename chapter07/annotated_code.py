"""
Chapter 7: LangSmith를 활용한 RAG 애플리케이션 평가
상세 주석이 포함된 전체 코드

이 파일은 notebook.ipynb의 모든 코드와 상세한 주석을 포함합니다.
각 패키지의 공식 문서를 기반으로 정확한 설명을 제공합니다.
"""

# ============================================================================
# 1. 환경 설정 및 API 키 구성
# ============================================================================

"""
필요한 패키지들:
- os: Python 표준 라이브러리, 운영 체제 인터페이스
- dotenv: .env 파일에서 환경 변수를 로드하는 서드파티 라이브러리
- langsmith: LangChain의 평가/모니터링 플랫폼
- langchain: LLM 애플리케이션 개발 프레임워크
- ragas: RAG (Retrieval-Augmented Generation) 평가 프레임워크
"""

import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
# .env 파일 형식: KEY=VALUE (예: OPENAI_API_KEY=sk-...)
load_dotenv()

# OpenAI API 설정 - GPT 모델 사용을 위한 필수 설정
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# LangSmith 추적 설정 - 디버깅과 모니터링을 위한 설정
os.environ["LANGCHAIN_TRACING_V2"] = "true"  # 추적 활성화
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"  # API 엔드포인트
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")  # 인증 키
os.environ["LANGCHAIN_PROJECT"] = "agent-book"  # 프로젝트 식별자

# Tavily API 설정 - 웹 검색 기능을 위한 설정
os.environ["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY")

# ============================================================================
# 2. 검색 대상 문서 로드
# ============================================================================

"""
GitLoader: Git 저장소에서 문서를 로드하는 특수 로더
- langchain_community 패키지의 일부
- Git 저장소를 클론하고 특정 파일들을 Document 객체로 변환
"""

from langchain_community.document_loaders import GitLoader

def file_filter(file_path: str) -> bool:
    """
    로드할 파일을 필터링하는 함수
    
    Args:
        file_path: 확인할 파일 경로
    
    Returns:
        bool: True면 로드, False면 스킵
    """
    return file_path.endswith(".md")  # Markdown 파일만 선택

# GitLoader 인스턴스 생성
loader = GitLoader(
    clone_url="https://github.com/langchain-ai/langchain",  # 저장소 URL
    repo_path="./langchain",  # 로컬 저장 경로
    branch="langchain==0.2.13",  # 특정 버전 태그
    file_filter=file_filter,  # 파일 필터 함수
)

# 문서 로드 - Document 객체 리스트 반환
documents = loader.load()
print(f"로드된 문서 수: {len(documents)}")

# 메타데이터 처리 - Ragas 호환성을 위한 필드 추가
for document in documents:
    document.metadata["filename"] = document.metadata["source"]

# ============================================================================
# 3. Ragas를 활용한 합성 테스트 데이터 생성
# ============================================================================

"""
Ragas (Retrieval-Augmented Generation Assessment System)
- RAG 시스템 평가를 위한 오픈소스 프레임워크
- 자동으로 테스트 질문과 답변을 생성
- 다양한 평가 메트릭 제공

주요 컴포넌트:
- TestsetGenerator: 테스트 데이터셋 생성기
- Evolution Types: 질문 생성 전략
  - simple: 단순 사실 기반 질문
  - reasoning: 추론이 필요한 질문
  - multi_context: 여러 문서를 참조해야 하는 질문
"""

import nest_asyncio  # 중첩된 비동기 실행 허용 (Jupyter 환경 필수)
from ragas.testset.generator import TestsetGenerator
from ragas.testset.evolutions import simple, reasoning, multi_context
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# Jupyter/Colab 환경에서 비동기 코드 실행 허용
nest_asyncio.apply()

# TestsetGenerator 초기화
generator = TestsetGenerator.from_langchain(
    # 테스트 데이터 생성용 LLM
    generator_llm=ChatOpenAI(model="gpt-4o"),
    
    # 생성된 데이터 품질 검증용 LLM
    critic_llm=ChatOpenAI(model="gpt-4o"),
    
    # 의미적 유사성 계산용 임베딩 모델
    embeddings=OpenAIEmbeddings(),
)

# 테스트셋 생성
testset = generator.generate_with_langchain_docs(
    documents,  # 소스 문서들
    test_size=4,  # 생성할 테스트 케이스 수
    distributions={  # 질문 타입별 분포
        simple: 0.5,  # 50% 단순 질문
        reasoning: 0.25,  # 25% 추론 질문
        multi_context: 0.25,  # 25% 복합 문맥 질문
    },
)

# ============================================================================
# 4. LangSmith Dataset 생성 및 저장
# ============================================================================

"""
LangSmith: LangChain의 평가/모니터링 플랫폼
- 테스트 데이터셋 관리
- 실행 추적 및 디버깅
- 성능 평가 및 비교
"""

from langsmith import Client

# LangSmith 클라이언트 초기화
client = Client()  # LANGCHAIN_API_KEY 환경변수 자동 사용

# 데이터셋 생성 (기존 것 삭제 후 새로 생성)
dataset_name = "agent-book"

if client.has_dataset(dataset_name=dataset_name):
    client.delete_dataset(dataset_name=dataset_name)

dataset = client.create_dataset(dataset_name=dataset_name)

# Ragas 테스트 데이터를 LangSmith 형식으로 변환
inputs = []  # 입력 질문들
outputs = []  # 예상 출력들
metadatas = []  # 추가 정보

for testset_record in testset.test_data:
    # 입력 데이터: 질문
    inputs.append({
        "question": testset_record.question,
    })
    
    # 출력 데이터: 참고 문맥과 정답
    outputs.append({
        "contexts": testset_record.contexts,
        "ground_truth": testset_record.ground_truth,
    })
    
    # 메타데이터: 소스 정보와 질문 타입
    metadatas.append({
        "source": testset_record.metadata[0]["source"],
        "evolution_type": testset_record.evolution_type,
    })

# LangSmith에 예제 데이터 추가
client.create_examples(
    inputs=inputs,
    outputs=outputs,
    metadata=metadatas,
    dataset_id=dataset.id,
)

# ============================================================================
# 5. 커스텀 Evaluator 구현
# ============================================================================

"""
RagasMetricEvaluator: Ragas 메트릭을 LangSmith와 통합하는 어댑터 클래스
- LangSmith의 평가 인터페이스와 Ragas 메트릭을 연결
- LLM과 임베딩 모델을 메트릭에 주입
"""

from typing import Any
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langsmith.schemas import Example, Run
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics.base import Metric, MetricWithEmbeddings, MetricWithLLM

class RagasMetricEvaluator:
    """
    Ragas 메트릭을 LangSmith 평가 시스템과 통합하는 클래스
    
    이 클래스는 어댑터 패턴을 사용하여 Ragas의 평가 메트릭을
    LangSmith의 evaluate 함수에서 사용할 수 있도록 변환합니다.
    """
    
    def __init__(self, metric: Metric, llm: BaseChatModel, embeddings: Embeddings):
        """
        Args:
            metric: Ragas 평가 메트릭 (context_precision, answer_relevancy 등)
            llm: 평가에 사용할 언어 모델
            embeddings: 텍스트 임베딩 모델
        """
        self.metric = metric
        
        # 메트릭이 LLM을 필요로 하는 경우 설정
        if isinstance(self.metric, MetricWithLLM):
            # LangChain LLM을 Ragas 형식으로 래핑
            self.metric.llm = LangchainLLMWrapper(llm)
            
        # 메트릭이 임베딩을 필요로 하는 경우 설정
        if isinstance(self.metric, MetricWithEmbeddings):
            # LangChain 임베딩을 Ragas 형식으로 래핑
            self.metric.embeddings = LangchainEmbeddingsWrapper(embeddings)
    
    def evaluate(self, run: Run, example: Example) -> dict[str, Any]:
        """
        실제 평가를 수행하는 메서드
        
        Args:
            run: LangSmith의 실행 결과 객체
            example: LangSmith의 예제 데이터 객체
        
        Returns:
            평가 결과 딕셔너리 {"key": 메트릭명, "score": 점수}
        """
        # Document 객체에서 텍스트 내용만 추출
        context_strs = [doc.page_content for doc in run.outputs["contexts"]]
        
        # Ragas 메트릭으로 점수 계산
        score = self.metric.score({
            "question": example.inputs["question"],
            "answer": run.outputs["answer"],
            "contexts": context_strs,
            "ground_truth": example.outputs["ground_truth"],
        })
        
        return {"key": self.metric.name, "score": score}

# ============================================================================
# 6. 평가 메트릭 설정
# ============================================================================

"""
Ragas 평가 메트릭:
- context_precision: 검색된 문서의 관련성 정확도
- answer_relevancy: 생성된 답변의 질문 관련성
- faithfulness: 답변이 제공된 문맥에 충실한 정도
- context_recall: 관련 정보의 검색 완전성
"""

from ragas.metrics import answer_relevancy, context_precision

# 사용할 메트릭 선택
metrics = [context_precision, answer_relevancy]

# 평가용 LLM 및 임베딩 모델 설정
llm = ChatOpenAI(model="gpt-4o", temperature=0)  # temperature=0: 일관된 평가
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Evaluator 인스턴스 생성
evaluators = [
    RagasMetricEvaluator(metric, llm, embeddings).evaluate
    for metric in metrics
]

# ============================================================================
# 7. RAG 체인 구현
# ============================================================================

"""
RAG (Retrieval-Augmented Generation) 체인:
1. 질문을 받아 관련 문서 검색
2. 검색된 문서를 컨텍스트로 사용
3. LLM이 컨텍스트 기반으로 답변 생성

주요 컴포넌트:
- Chroma: 벡터 데이터베이스
- Retriever: 유사도 검색 인터페이스
- RunnableParallel: 병렬 실행을 위한 LangChain 컴포넌트
- ChatPromptTemplate: 프롬프트 템플릿
"""

from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough

# 벡터 데이터베이스 생성
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
db = Chroma.from_documents(documents, embeddings)

# 프롬프트 템플릿 정의
prompt = ChatPromptTemplate.from_template('''
다음 문맥만을 고려해 질문에 답하세요.

문맥: """
{context}
"""

질문: {question}
''')

# LLM 모델 설정
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 검색기 생성
retriever = db.as_retriever()

# RAG 체인 구성
chain = RunnableParallel({
    "question": RunnablePassthrough(),  # 질문을 그대로 전달
    "context": retriever,  # 질문으로 문서 검색
}).assign(
    answer=prompt | model | StrOutputParser()  # 프롬프트 → LLM → 텍스트 파싱
)

# ============================================================================
# 8. 추론 함수 정의
# ============================================================================

def predict(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    LangSmith evaluate 함수에서 사용할 추론 함수
    
    Args:
        inputs: {"question": str} 형식의 입력
    
    Returns:
        {"contexts": list, "answer": str} 형식의 출력
    """
    question = inputs["question"]
    output = chain.invoke(question)
    
    return {
        "contexts": output["context"],  # 검색된 문서들
        "answer": output["answer"],  # 생성된 답변
    }

# ============================================================================
# 9. 오프라인 평가 실행
# ============================================================================

"""
LangSmith의 evaluate 함수:
- 데이터셋의 각 예제에 대해 추론 수행
- 각 결과를 evaluator로 평가
- 결과를 LangSmith 대시보드에 기록
"""

from langsmith.evaluation import evaluate

# 평가 실행
results = evaluate(
    predict,  # 추론 함수
    data="agent-book",  # 데이터셋 이름
    evaluators=evaluators,  # 평가 메트릭들
)

# ============================================================================
# 10. 온라인 평가 - 피드백 시스템
# ============================================================================

"""
온라인 평가: 실제 사용자로부터 피드백을 수집하는 시스템
- 사용자가 생성된 답변에 대해 Good/Bad 피드백 제공
- 피드백은 LangSmith에 저장되어 분석 가능
"""

from uuid import UUID
import ipywidgets as widgets
from IPython.display import display

def display_feedback_buttons(run_id: UUID) -> None:
    """
    Jupyter 노트북에서 피드백 버튼을 표시하는 함수
    
    Args:
        run_id: LangSmith 실행 ID
    """
    # 버튼 위젯 생성
    good_button = widgets.Button(
        description="Good",
        button_style="success",  # 녹색 스타일
        icon="thumbs-up",
    )
    bad_button = widgets.Button(
        description="Bad",
        button_style="danger",  # 빨간색 스타일
        icon="thumbs-down",
    )
    
    # 버튼 클릭 핸들러
    def on_button_clicked(button: widgets.Button) -> None:
        # 버튼에 따라 점수 할당
        if button == good_button:
            score = 1
        elif button == bad_button:
            score = 0
        else:
            raise ValueError(f"Unknown button: {button}")
        
        # LangSmith에 피드백 전송
        client = Client()
        client.create_feedback(
            run_id=run_id,
            key="thumbs",  # 피드백 타입
            score=score,  # 점수 (0 또는 1)
        )
        print("피드백을 전송했습니다")
    
    # 이벤트 핸들러 등록
    good_button.on_click(on_button_clicked)
    bad_button.on_click(on_button_clicked)
    
    # 버튼 표시
    display(good_button, bad_button)

# ============================================================================
# 11. 실행 추적과 피드백 수집
# ============================================================================

"""
collect_runs: LangSmith 실행 추적을 위한 컨텍스트 매니저
- with 블록 내의 모든 LangChain 실행을 추적
- 실행 ID를 가져와 피드백과 연결 가능
"""

from langchain_core.tracers.context import collect_runs

# 실행 추적과 함께 체인 실행
with collect_runs() as runs_cb:
    output = chain.invoke("LangChain의 개요를 알려줘")
    print(output["answer"])
    
    # 실행 ID 추출
    run_id = runs_cb.traced_runs[0].id

# 피드백 버튼 표시
display_feedback_buttons(run_id)

# ============================================================================
# 주요 패키지 요약
# ============================================================================

"""
1. LangChain (langchain, langchain_core, langchain_community)
   - 공식 문서: https://python.langchain.com/
   - LLM 애플리케이션 개발을 위한 종합 프레임워크
   - 체인, 프롬프트, 메모리, 에이전트 등 제공

2. Ragas (ragas)
   - 공식 문서: https://docs.ragas.io/
   - RAG 시스템 평가를 위한 전문 프레임워크
   - 자동 테스트 생성 및 다양한 평가 메트릭 제공

3. LangSmith (langsmith)
   - 공식 문서: https://docs.smith.langchain.com/
   - LangChain 애플리케이션의 추적, 평가, 모니터링
   - 프로덕션 환경의 성능 분석 도구

4. ChromaDB (chromadb, langchain_chroma)
   - 공식 문서: https://docs.trychroma.com/
   - 오픈소스 벡터 데이터베이스
   - 임베딩 저장 및 유사도 검색

5. OpenAI (openai, langchain_openai)
   - 공식 문서: https://platform.openai.com/docs
   - GPT 모델 및 임베딩 API 제공
   - ChatGPT, GPT-4 등 최신 언어 모델 접근

6. nest_asyncio
   - 공식 문서: https://github.com/erdewit/nest_asyncio
   - Jupyter 환경에서 중첩 비동기 실행 지원
   - asyncio 이벤트 루프 충돌 해결

7. python-dotenv
   - 공식 문서: https://github.com/theskumar/python-dotenv
   - 환경 변수를 .env 파일에서 로드
   - 민감한 정보 관리의 모범 사례
"""
