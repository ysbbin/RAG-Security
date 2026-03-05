# RAG Security Experiment: Prompt Injection 취약성 분석 및 방어 전략 비교

## 프로젝트 개요

RAG(Retrieval-Augmented Generation) 시스템에서 외부 문서에 악성 지시가 포함됐을 때
LLM이 얼마나 취약한지 실험으로 측정하고, 효과적인 방어 전략을 비교 분석하는 프로젝트.

**목적:** ML 엔지니어 / AI 보안 포트폴리오용 실험 프로젝트  
**기간:** 4~5주  
**환경:** Windows 로컬, CPU only (GPU 불필요)

---

## 연구 질문

> "RAG 시스템에서 retrieved context에 악성 지시가 포함됐을 때,
> LLM은 얼마나 속는가? 그리고 어떤 방어 전략이 가장 효과적인가?"

---

## 폴더 구조

```
rag-security-experiment/
├── data/
│   ├── raw/               # HotpotQA 원본 데이터
│   └── attack/            # 생성된 악성 문서 데이터
│       ├── direct/        # Direct Injection 샘플
│       ├── indirect/      # Indirect Injection 샘플
│       └── manipulation/  # Context Manipulation 샘플
├── src/
│   ├── chunking.py        # Chunking 전략 구현 (Fixed / Sentence / Semantic)
│   ├── retrieval.py       # 벡터 DB 구축 및 검색 파이프라인
│   ├── attack.py          # 악성 문서 자동 생성 스크립트
│   ├── defense.py         # 방어 전략 구현
│   └── evaluate.py        # 실험 평가 지표 계산
├── experiments/
│   ├── results/           # 실험 결과 JSON 저장
│   └── logs/              # 실험 로그
├── notebooks/
│   ├── 01_eda.ipynb        # 데이터 탐색
│   ├── 02_attack_exp.ipynb # 공격 실험 분석
│   └── 03_defense_exp.ipynb# 방어 실험 분석
├── .env                   # API 키 (git 제외)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 기술 스택

| 역할 | 라이브러리 |
|---|---|
| RAG 파이프라인 | `langchain` |
| 벡터 DB | `chromadb` |
| 임베딩 모델 | `sentence-transformers` (로컬, 무료) |
| LLM | `openai` GPT-4o-mini or `groq` LLaMA3 |
| 데이터셋 | `datasets` (HuggingFace) |
| 환경변수 | `python-dotenv` |
| 분석 & 시각화 | `pandas`, `matplotlib`, `seaborn` |

---

## 데이터

### 정상 데이터
- **HotpotQA** (distractor split) — HuggingFace에서 다운로드
  - 다중 문서 기반 QA 데이터셋
  - 질문 100개 + 관련 문서 사용
  - 로드 방법:
    ```python
    from datasets import load_dataset
    ds = load_dataset("hotpot_qa", "distractor")
    ```

### 악성 데이터 (자동 생성)
정상 문서에 악성 지시를 덧붙이는 방식으로 `src/attack.py`가 자동 생성

| 공격 유형 | 설명 | 샘플 수 |
|---|---|---|
| Direct Injection | 노골적인 지시 삽입 | 100개 |
| Indirect Injection | 교묘하게 숨긴 지시 | 100개 |
| Context Manipulation | 사실 정보 왜곡 | 100개 |

---

## 실험 설계

### 실험 1 — 공격 성공률 측정 (Attack Experiment)

**독립변수 (바꿔가며 실험)**
- 공격 유형: Direct / Indirect / Manipulation
- 악성 문서 위치: 검색 결과 1위 / 3위 / 5위
- Chunking 전략: Fixed-size / Sentence-based / Semantic

**종속변수 (측정 지표)**
- ASR (Attack Success Rate): 공격 성공 비율
- Answer Accuracy: 정상 답변 정확도 변화
- Compliance Rate: LLM이 악성 지시를 따른 비율

### 실험 2 — 방어 전략 효과 비교 (Defense Experiment)

**구현할 방어 전략 3가지**

1. **Input Filtering** — retrieved 문서에서 악성 패턴 키워드 감지 및 제거
2. **System Prompt Hardening** — 시스템 프롬프트에 문서 내 지시 무시 명령 추가
3. **Context Sandboxing** — retrieved 문서를 `[DOCUMENT]` 태그로 감싸 LLM에 전달

**측정 지표**
- Defense Success Rate: 각 방어 전략의 공격 차단율
- False Positive Rate: 정상 문서를 악성으로 잘못 판단한 비율
- Latency: 방어 적용 전후 응답 속도 차이

---

## 구현 순서

### 1단계 (1주차) — 기본 RAG 파이프라인 구축
- [ ] `requirements.txt` 및 환경 세팅
- [ ] HotpotQA 데이터 다운로드 및 전처리
- [ ] Chunking 전략 3가지 구현 (`src/chunking.py`)
- [ ] ChromaDB 벡터 DB 구축 및 검색 구현 (`src/retrieval.py`)
- [ ] 정상 RAG 파이프라인 동작 확인

### 2단계 (2~3주차) — 공격 시나리오 실험
- [ ] 악성 문서 자동 생성 스크립트 (`src/attack.py`)
- [ ] 공격 유형별 실험 실행
- [ ] 결과 저장 및 ASR 계산 (`src/evaluate.py`)
- [ ] 실험 결과 시각화 (`notebooks/02_attack_exp.ipynb`)

### 3단계 (4주차) — 방어 전략 구현 및 비교
- [ ] 방어 전략 3가지 구현 (`src/defense.py`)
- [ ] 방어 적용 후 실험 재실행
- [ ] 공격 vs 방어 성능 비교 시각화 (`notebooks/03_defense_exp.ipynb`)

### 4단계 (5주차) — 분석 및 리포트 작성
- [ ] 전체 실험 결과 종합 분석
- [ ] README 논문 형식으로 작성
- [ ] PDF 리포트 작성 (4~6페이지)

---

## 평가 지표 계산 방법

```python
# Attack Success Rate (ASR)
ASR = (공격 성공 횟수 / 전체 실험 횟수) * 100

# Answer Accuracy
Accuracy = (정답 횟수 / 전체 질문 수) * 100

# Defense Success Rate
DSR = (방어 성공 횟수 / 전체 공격 시도 수) * 100
```

---

## 주요 참고 논문

1. **Prompt Injection Attacks and Defenses in LLM-Integrated Applications** (Liu et al., 2023)
2. **Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injections** (Greshake et al., 2023)
3. **Lost in the Middle: How Language Models Use Long Contexts** (Liu et al., 2023)
4. **Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection** (Asai et al., 2023)

---

## 환경변수 (.env)

```
OPENAI_API_KEY=your_openai_api_key_here
GROQ_API_KEY=your_groq_api_key_here   # 무료 대안
```

---

## Claude Code 활용 가이드

이 파일을 읽은 후 아래 순서로 작업 요청할 것:

1. `requirements.txt` 생성
2. `.gitignore` 생성 (`.env`, `data/raw/`, `__pycache__` 등 포함)
3. `src/chunking.py` — Fixed / Sentence / Semantic chunking 구현
4. `src/retrieval.py` — ChromaDB 기반 RAG 파이프라인 구현
5. `src/attack.py` — 악성 문서 자동 생성 스크립트
6. `src/defense.py` — 방어 전략 3가지 구현
7. `src/evaluate.py` — 평가 지표 계산 함수
8. `notebooks/01_eda.ipynb` — 데이터 탐색 노트북

작업 요청 예시:
> "PROJECT_OVERVIEW.md를 읽었어. 지금은 1단계야.
> requirements.txt랑 src/chunking.py부터 만들어줘."
