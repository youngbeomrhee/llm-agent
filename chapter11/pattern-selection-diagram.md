# Agent Design Pattern Selection Diagrams

## 1. 패턴 선택 의사결정 플로우차트

```mermaid
flowchart TD
    Start([Agent 설계 시작])

    Start --> Q1{환경 정보<br/>캡처 필요?}

    Q1 -->|Yes| ProactiveGoal[Proactive Goal Creator<br/>+ 접근성, 목표 탐색<br/>- 오버헤드]
    Q1 -->|No| PassiveGoal[Passive Goal Creator<br/>+ 효율성, 상호작용<br/>- 추론 불확실성]

    ProactiveGoal --> Q2{프롬프트<br/>최적화 필요?}
    PassiveGoal --> Q2

    Q2 -->|Yes| PromptOpt[Prompt/Response Optimiser<br/>+ 표준화, 목표 정렬<br/>- 유지보수 오버헤드]
    Q2 -->|No| Q3{외부 데이터<br/>저장소 사용?}

    PromptOpt --> Q3

    Q3 -->|Yes| RAG[Retrieval Augmented Generation<br/>+ 지식 검색, 데이터 프라이버시<br/>- 유지보수 오버헤드]
    Q3 -->|No| Q4{FM 쿼리<br/>횟수?}

    RAG --> Q4

    Q4 -->|한 번| OneShot[One-shot Model Querying<br/>+ 비용 효율성, 단순성<br/>- 과도한 단순화]
    Q4 -->|여러 번| Incremental[Incremental Model Querying<br/>+ 추론 확실성, 설명 가능성<br/>- 오버헤드]

    OneShot --> Q5{계획 생성<br/>방식?}
    Incremental --> Q5

    Q5 -->|단일 경로| SinglePath[Single-path Plan Generator<br/>+ 효율성, 일관성<br/>- 유연성 부족]
    Q5 -->|다중 경로| MultiPath[Multi-path Plan Generator<br/>+ 인간 선호 정렬, 포괄성<br/>- 오버헤드]

    SinglePath --> Q6{계획 검토<br/>필요?}
    MultiPath --> Q6

    Q6 -->|No| Q7{FM 입출력<br/>제어 필요?}
    Q6 -->|Yes| ReflectionType{검토 주체?}

    ReflectionType -->|자체| SelfRef[Self-reflection<br/>+ 지속적 개선, 효율성<br/>- 추론 불확실성]
    ReflectionType -->|다른 에이전트| CrossRef[Cross-reflection<br/>+ 확장성, 포괄성<br/>- 복잡한 책임성]
    ReflectionType -->|인간| HumanRef[Human Reflection<br/>+ 인간 선호 정렬, 이의제기<br/>- 공정성 보존 어려움]

    SelfRef --> Q7
    CrossRef --> CoopType{협력 방식?}
    HumanRef --> Q7

    CoopType -->|투표| Voting[Voting-based Cooperation<br/>+ 공정성, 책임성<br/>- 중앙화]
    CoopType -->|역할| RoleBased[Role-based Cooperation<br/>+ 업무 분담, 확장성<br/>- 오버헤드]
    CoopType -->|토론| Debate[Debate-based Cooperation<br/>+ 적응성, 설명 가능성<br/>- 제한된 능력]

    Voting --> Q7
    RoleBased --> Q7
    Debate --> Q7

    Q7 -->|Yes| Guardrails[Multimodal Guardrails<br/>+ 견고성, 안전성<br/>- 설명 가능성 부족]
    Q7 -->|No| Q8{외부 도구/<br/>에이전트 사용?}

    Guardrails --> Q8

    Q8 -->|Yes| Registry[Tool/Agent Registry<br/>+ 검색 가능성, 효율성<br/>- 중앙화]
    Q8 -->|No| Q9{성능 평가<br/>필요?}

    Registry --> Adapter[Agent Adapter<br/>+ 상호운용성, 적응성<br/>- 유지보수 오버헤드]

    Adapter --> Q9

    Q9 -->|Yes| Evaluator[Agent Evaluator<br/>+ 기능 적합성, 적응성<br/>- 메트릭 정량화 어려움]
    Q9 -->|No| End([설계 완료])

    Evaluator --> End

    style ProactiveGoal fill:#e1f5e1
    style PassiveGoal fill:#e1f5e1
    style PromptOpt fill:#fff4e1
    style RAG fill:#e1f0ff
    style OneShot fill:#ffe1f0
    style Incremental fill:#ffe1f0
    style SinglePath fill:#f0e1ff
    style MultiPath fill:#f0e1ff
    style SelfRef fill:#ffe1e1
    style CrossRef fill:#ffe1e1
    style HumanRef fill:#ffe1e1
    style Voting fill:#e1ffe1
    style RoleBased fill:#e1ffe1
    style Debate fill:#e1ffe1
    style Guardrails fill:#fff5e1
    style Registry fill:#e1f5ff
    style Adapter fill:#e1f5ff
    style Evaluator fill:#f5e1ff
```

## 2. 패턴 카테고리 및 관계도

```mermaid
graph TB
    subgraph Goal_Creation[목표 생성]
        P1[Passive Goal Creator]
        P2[Proactive Goal Creator]
    end

    subgraph Context_Management[컨텍스트 관리]
        P3[Prompt/Response Optimiser]
        P4[RAG]
    end

    subgraph Model_Querying[모델 쿼리]
        P5[One-shot Model Querying]
        P6[Incremental Model Querying]
    end

    subgraph Plan_Generation[계획 생성]
        P7[Single-path Plan Generator]
        P8[Multi-path Plan Generator]
    end

    subgraph Reflection[반영/검토]
        P9[Self-reflection]
        P10[Cross-reflection]
        P11[Human Reflection]
    end

    subgraph Multi_Agent[다중 에이전트 협력]
        P12[Voting-based Cooperation]
        P13[Role-based Cooperation]
        P14[Debate-based Cooperation]
    end

    subgraph Safety_Integration[안전성 및 통합]
        P15[Multimodal Guardrails]
        P16[Tool/Agent Registry]
        P17[Agent Adapter]
    end

    subgraph Evaluation[평가]
        P18[Agent Evaluator]
    end

    P1 -.대안.-> P2
    P1 --> P3
    P2 --> P3
    P2 --> P15

    P3 --> P9
    P3 --> P10
    P3 --> P11
    P3 --> P17

    P4 -.보완.-> P1
    P4 -.보완.-> P2
    P4 -.보완.-> P3

    P5 -.대안.-> P6
    P5 --> P7
    P5 --> P15

    P6 --> P8
    P6 --> P9
    P6 --> P11
    P6 --> P15

    P7 -.대안.-> P8
    P7 --> P9

    P8 --> P11

    P9 --> P3
    P9 --> P6
    P9 --> P7

    P10 --> P3
    P10 --> P12
    P10 --> P13
    P10 --> P14
    P10 --> P16

    P11 --> P3
    P11 --> P8
    P11 --> P6

    P12 -.대안.-> P13
    P12 -.대안.-> P14
    P12 --> P16

    P13 -.보완.-> P12
    P13 -.보완.-> P14
    P13 --> P16

    P14 -.보완.-> P12
    P14 -.보완.-> P13
    P14 --> P16

    P15 --> P2
    P15 --> P5
    P15 --> P6

    P16 --> P10
    P16 --> P12
    P16 --> P13
    P16 --> P14
    P16 --> P17

    P17 --> P3
    P17 --> P16

    P18 -.평가.-> P1
    P18 -.평가.-> P2
    P18 -.평가.-> P3
    P18 -.평가.-> P9
    P18 -.평가.-> P15

    style P1 fill:#e1f5e1
    style P2 fill:#e1f5e1
    style P3 fill:#fff4e1
    style P4 fill:#e1f0ff
    style P5 fill:#ffe1f0
    style P6 fill:#ffe1f0
    style P7 fill:#f0e1ff
    style P8 fill:#f0e1ff
    style P9 fill:#ffe1e1
    style P10 fill:#ffe1e1
    style P11 fill:#ffe1e1
    style P12 fill:#e1ffe1
    style P13 fill:#e1ffe1
    style P14 fill:#e1ffe1
    style P15 fill:#fff5e1
    style P16 fill:#e1f5ff
    style P17 fill:#e1f5ff
    style P18 fill:#f5e1ff
```

## 3. 패턴 간 관계 타입 (ERD 스타일)

```mermaid
erDiagram
    GOAL_CREATION ||--|| CONTEXT_MANAGEMENT : enhances
    GOAL_CREATION ||--o{ REFLECTION : receives_feedback
    GOAL_CREATION }o--|| SAFETY : protected_by

    CONTEXT_MANAGEMENT ||--|| MODEL_QUERYING : provides_input
    CONTEXT_MANAGEMENT ||--o{ REFLECTION : optimizes_with
    CONTEXT_MANAGEMENT ||--o{ INTEGRATION : interfaces_with

    MODEL_QUERYING ||--|| PLAN_GENERATION : generates
    MODEL_QUERYING ||--o{ REFLECTION : supports
    MODEL_QUERYING }o--|| SAFETY : controlled_by

    PLAN_GENERATION ||--o{ REFLECTION : reviewed_by
    PLAN_GENERATION ||--o{ EXECUTION : executed_by

    REFLECTION ||--o{ MULTI_AGENT : coordinates
    REFLECTION ||--|| CONTEXT_MANAGEMENT : improves

    MULTI_AGENT ||--|| INTEGRATION : discovers_via
    MULTI_AGENT }o--|| REFLECTION : provides_feedback

    SAFETY ||--o{ GOAL_CREATION : filters
    SAFETY ||--o{ MODEL_QUERYING : manages

    INTEGRATION ||--|| EXECUTION : enables
    INTEGRATION ||--|| MULTI_AGENT : supports

    EVALUATION ||--o{ ALL_PATTERNS : assesses

    GOAL_CREATION {
        string Passive_Goal_Creator
        string Proactive_Goal_Creator
    }

    CONTEXT_MANAGEMENT {
        string Prompt_Response_Optimiser
        string RAG
    }

    MODEL_QUERYING {
        string One_shot_Querying
        string Incremental_Querying
    }

    PLAN_GENERATION {
        string Single_path_Generator
        string Multi_path_Generator
    }

    REFLECTION {
        string Self_reflection
        string Cross_reflection
        string Human_Reflection
    }

    MULTI_AGENT {
        string Voting_based
        string Role_based
        string Debate_based
    }

    SAFETY {
        string Multimodal_Guardrails
    }

    INTEGRATION {
        string Tool_Agent_Registry
        string Agent_Adapter
    }

    EVALUATION {
        string Agent_Evaluator
    }

    EXECUTION {
        string Task_Execution
    }

    ALL_PATTERNS {
        string all_18_patterns
    }
```

## 4. 패턴 선택 매트릭스

| 요구사항 | 추천 패턴 | 대안 패턴 | 보완 패턴 |
|---------|----------|----------|----------|
| **접근성 향상** | Proactive Goal Creator | Passive Goal Creator | Multimodal Guardrails |
| **효율성 우선** | One-shot Model Querying, Passive Goal Creator | Incremental Model Querying | Single-path Plan Generator |
| **추론 확실성** | Incremental Model Querying, Self-reflection | One-shot Model Querying | Cross-reflection, RAG |
| **인간 선호 정렬** | Human Reflection, Multi-path Plan Generator | Self-reflection | Prompt/Response Optimiser |
| **확장성** | Role-based Cooperation, Cross-reflection | Voting-based Cooperation | Tool/Agent Registry |
| **데이터 프라이버시** | RAG | Fine-tuning | Multimodal Guardrails |
| **비용 최적화** | One-shot Model Querying | Incremental Model Querying | Self-reflection |
| **설명 가능성** | Incremental Model Querying, Self-reflection | One-shot Model Querying | Human Reflection, Debate-based |
| **안전성** | Multimodal Guardrails | Human Reflection | Self-reflection |
| **상호운용성** | Agent Adapter, Tool/Agent Registry | - | Prompt/Response Optimiser |
| **공정성** | Voting-based Cooperation | Role-based Cooperation | Human Reflection |
| **적응성** | Debate-based Cooperation, Agent Adapter | Role-based Cooperation | Agent Evaluator |

## 5. 패턴 조합 예시

### 예시 1: 고신뢰성 에이전트
```mermaid
graph LR
    A[Passive Goal Creator] --> B[Prompt/Response Optimiser]
    B --> C[RAG]
    C --> D[Incremental Model Querying]
    D --> E[Single-path Plan Generator]
    E --> F[Self-reflection]
    F --> G[Multimodal Guardrails]
    G --> H[Agent Evaluator]
```

### 예시 2: 협업 에이전트 시스템
```mermaid
graph LR
    A[Proactive Goal Creator] --> B[Multi-path Plan Generator]
    B --> C[Cross-reflection]
    C --> D[Role-based Cooperation]
    D --> E[Tool/Agent Registry]
    E --> F[Agent Adapter]
    F --> G[Agent Evaluator]
```

### 예시 3: 인간 중심 에이전트
```mermaid
graph LR
    A[Passive Goal Creator] --> B[Incremental Model Querying]
    B --> C[Multi-path Plan Generator]
    C --> D[Human Reflection]
    D --> E[Multimodal Guardrails]
    E --> F[Agent Evaluator]
```

### 예시 4: 비용 효율적 에이전트
```mermaid
graph LR
    A[Passive Goal Creator] --> B[One-shot Model Querying]
    B --> C[Single-path Plan Generator]
    C --> D[Self-reflection]
    D --> E[Agent Evaluator]
```

## 6. 패턴 선택 체크리스트

### Step 1: 목표 생성 방식 결정
- [ ] 사용자가 명확한 프롬프트를 제공하는가? → Passive Goal Creator
- [ ] 멀티모달 컨텍스트 캡처가 필요한가? → Proactive Goal Creator
- [ ] 접근성이 중요한가? → Proactive Goal Creator

### Step 2: 컨텍스트 관리 결정
- [ ] 프롬프트 표준화가 필요한가? → Prompt/Response Optimiser
- [ ] 외부 지식 베이스가 필요한가? → RAG
- [ ] 데이터 프라이버시가 중요한가? → RAG

### Step 3: 모델 쿼리 전략 결정
- [ ] 비용이 제한적인가? → One-shot Model Querying
- [ ] 상세한 추론 과정이 필요한가? → Incremental Model Querying
- [ ] 설명 가능성이 중요한가? → Incremental Model Querying

### Step 4: 계획 생성 방식 결정
- [ ] 효율성이 최우선인가? → Single-path Plan Generator
- [ ] 사용자 맞춤화가 필요한가? → Multi-path Plan Generator
- [ ] 복잡한 작업인가? → Multi-path Plan Generator

### Step 5: 검토 메커니즘 결정
- [ ] 자동화된 검토가 필요한가? → Self-reflection
- [ ] 다양한 관점이 필요한가? → Cross-reflection
- [ ] 인간의 판단이 중요한가? → Human Reflection

### Step 6: 협력 방식 결정 (다중 에이전트의 경우)
- [ ] 공정한 의사결정이 필요한가? → Voting-based
- [ ] 전문화된 역할 분담이 필요한가? → Role-based
- [ ] 적응적 학습이 필요한가? → Debate-based

### Step 7: 안전성 및 통합 결정
- [ ] 입출력 제어가 필요한가? → Multimodal Guardrails
- [ ] 외부 도구/에이전트 관리가 필요한가? → Tool/Agent Registry
- [ ] 도구 인터페이스 변환이 필요한가? → Agent Adapter

### Step 8: 평가 결정
- [ ] 성능 평가가 필요한가? → Agent Evaluator

## 7. 패턴 적용 우선순위

```mermaid
graph TD
    subgraph Priority_1[우선순위 1: 핵심 기능]
        Core1[Goal Creator<br/>Passive/Proactive]
        Core2[Plan Generator<br/>Single/Multi-path]
    end

    subgraph Priority_2[우선순위 2: 품질 향상]
        Quality1[Reflection<br/>Self/Cross/Human]
        Quality2[Model Querying<br/>One-shot/Incremental]
    end

    subgraph Priority_3[우선순위 3: 최적화]
        Opt1[Prompt/Response Optimiser]
        Opt2[RAG]
    end

    subgraph Priority_4[우선순위 4: 안전성]
        Safety1[Multimodal Guardrails]
    end

    subgraph Priority_5[우선순위 5: 확장]
        Ext1[Multi-Agent Cooperation]
        Ext2[Tool/Agent Registry]
        Ext3[Agent Adapter]
    end

    subgraph Priority_6[우선순위 6: 검증]
        Val1[Agent Evaluator]
    end

    Priority_1 --> Priority_2
    Priority_2 --> Priority_3
    Priority_3 --> Priority_4
    Priority_4 --> Priority_5
    Priority_5 --> Priority_6
```

## 범례

**관계 타입:**
- 실선 화살표 (→): 직접적인 연결/의존성
- 점선 화살표 (-.->): 대안 관계
- 이중선 (==>): 강한 의존성
- "보완": 함께 사용하면 시너지

**색상 의미:**
- 🟢 녹색: 목표 생성 관련
- 🟡 노란색: 컨텍스트 관리
- 🔵 파란색: 데이터/지식 관련
- 🔴 분홍/빨강: 추론 및 검토
- 🟣 보라: 계획 생성
- 🟠 주황: 안전성
- 🔷 청록: 통합 및 도구
