# 서울시 청년정책 공문서-민원 통합 GraphRAG 시스템

> 발표자료: [https://docs.google.com/presentation/d/14w9O2muEAtX1wCSyr8blcgLKZR_diBEYmZjQwv0opMI/edit?usp=sharing](https://docs.google.com/presentation/d/14w9O2muEAtX1wCSyr8blcgLKZR_diBEYmZjQwv0opMI/edit?usp=sharing)

이 프로젝트는 **서울시 청년수당 공문서**와 **민원 답변 데이터**를 결합하여, 민원 사례로부터 정책적 근거(공문서)와 담당자를 추적할 수 있는 **고도화된 Graph Retrieval-Augmented Generation (GraphRAG)** 시스템입니다.

단순히 텍스트만 찾는 기존 RAG의 한계를 넘어, **벡터 유사도**와 **지식 그래프의 관계망**을 동시에 활용하여 질문에 대한 정확한 출처와 근거를 제시합니다.

---

## 🏗️ 시스템 아키텍처 및 데이터 구조

### 1. 지식 그래프 (Knowledge Graph)
*   **노드**: `Document` (공문서), `Complaint` (민원), `Person` (작성자), `Department` (부서).
*   **관계**: 
    *   `AUTHORED`: 작성자 -> 문서
    *   `BELONGS_TO`: 작성자 -> 부서
    *   `CITES`: 문서 -> 문서 (인용 및 참조 관계)
    *   `RELATED_TO`: 민원 -> 공문서 (벡터 유사도 기반 연결, **Top 5**)

### 2. 하이브리드 검색 (Hybrid Retrieval)
*   사용자 질문에 대해 **공문서 본문**과 **민원 본문**을 각각의 벡터 인덱스에서 동시 검색.
*   검색된 노드로부터 그래프 탐색을 수행하여 관련 담당자, 부서, 그리고 인용된 근거 문서들까지 확보 (Multi-hop Trace).

---

## 📂 프로젝트 구조

```text
sinoic-hackerton/
├── data/                 # 공문서 및 민원 CSV 데이터 파일
├── docs/                 # 원본 문서(attachments) 및 파싱된 마크다운 파일
├── scripts/              # 데이터 수집, 파싱 및 관계 추출 스크립트
├── graph_db/             # Graph DB 연동, 데이터 로딩 및 API 서버
│   ├── .venv/            # 파이썬 가상환경
│   ├── static/           # API 서버 정적 대시보드 파일 (시각화 UI)
│   └── api_server_real.py # 최종 API 서버 스크립트
├── logs/                 # 데이터 처리 및 파싱 에러 로그
├── .env                  # 환경 변수 (OpenAI API Key, Neo4j 접속 정보 등)
└── README.md             # 프로젝트 통합 설명서
```

---

## 🚀 설치 및 실행 방법

### ⚡ 빠른 실행 (통합 스크립트)
환경 설정, 데이터 구축, 서버 실행까지 한 번에 완료하려면 다음 명령어를 실행하세요:
```bash
./setup_and_run.sh
```
*(최초 실행 시 `.env` 파일이 생성되며, `OPENAI_API_KEY`를 입력한 후 다시 실행하시면 됩니다.)*

---

### 🛠️ 수동 실행 (상세 단계)

### 0. Neo4j 데이터베이스 실행 (Docker)
Neo4j가 설치되어 있지 않다면 도커를 사용하여 간편하게 실행할 수 있습니다.
```bash
docker run \
    --name neo4j-hackerton \
    -p 7474:7474 -p 7687:7687 \
    -d \
    -e NEO4J_AUTH=neo4j/testpassword \
    -e NEO4J_PLUGINS='["apoc"]' \
    neo4j:5.26.0
```
*   **ID**: `neo4j` / **PW**: `testpassword`
*   브라우저 접속: `http://localhost:7474`
*   데이터 접속: `bolt://localhost:7687`

### 1. 환경 설정
*   **필수 요구사항**: Python 3.12+, Neo4j DB, OpenAI API Key.
*   **의존성 설치** (프로젝트 루트에서 실행):
    ```bash
    uv sync
    ```
*   **.env 파일 작성** (프로젝트 루트 디렉토리에 생성):
    ```env
    OPENAI_API_KEY=sk-proj-...
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=testpassword
    ```

### 2. 데이터베이스 구축 (프로젝트 루트에서 실행)
최초 1회 실행하여 그래프를 생성하고 벡터 인덱스를 빌드합니다.
```bash
# 1. 공문서 기초 데이터(제목, 인용 관계) 구축
uv run graph_db/301_build_real_graph.py

# 2. 공문서 본문(MD 파일) 업데이트 및 벡터 인덱스 생성
uv run graph_db/302_update_doc_content.py

# 3. 민원 데이터 추가 및 공문서-민원 유사도 연결 (Top 5)
uv run graph_db/303_add_complaints_node.py
```

### 3. API 서버 및 웹 UI 실행
```bash
# 서버 실행 (기본 포트 8000)
uv run uvicorn graph_db.api_server_real:app --host 0.0.0.0 --port 8000 --reload
```
서버 실행 후 브라우저에서 `http://localhost:8000/`으로 접속하면 **통합 검색 및 그래프 시각화 대시보드**를 사용할 수 있습니다.

---

## 🌐 API 가이드

### 1. 검색 API (`POST /api/search`)
*   사용자 질문에 대해 하이브리드 검색을 수행하고, 답변과 함께 관련 공문서/민원 노드 및 담당자 정보를 반환합니다.
*   **Payload**: `{ "query": "서류 미비로 지급이 중단된 경우의 해결책은?" }`

### 2. 그래프 시각화 API (`GET /api/graph/overview`)
*   UI에서 지식 그래프의 구조를 시각화할 수 있도록 노드와 관계 데이터를 반환합니다.

---

## 📝 주요 문제 해결 및 트러블슈팅 기록

### APOC 플러그인 의존성 제거
LangChain의 기본 `Neo4jGraph`가 요구하는 APOC 플러그인 없이도 동작하도록 `refresh_schema=False` 옵션과 수동 스키마 주입 방식을 사용하여 환경 호환성을 확보했습니다.

### 데이터 정제 (Data Cleaning)
CSV 데이터 로드 시 포함될 수 있는 `\r` 등의 숨은 공백으로 인한 Cypher 매칭 실패를 방지하기 위해 모든 데이터 삽입 및 조회 단계에 `.strip()` 처리를 적용했습니다.

### 추적성 강화 (Multi-hop Trace)
단순한 1-hop 검색을 넘어, **민원 -> 공문서 -> 작성자 -> 부서**로 이어지는 관계망을 최적화된 Cypher 쿼리로 탐색하여 답변의 근거를 명확히 제시합니다.

### 벡터 인덱스 초기화 이슈
`Neo4jVector.from_existing_graph` 사용 시 필수 인자인 `embedding_node_property` 설정 및 인덱스 이름 불일치 문제를 해결하여 대용량 본문 데이터에 대한 고속 벡터 검색을 안정화했습니다.

---
**Sinoic Tech Hackathon - GraphRAG Team**

---

## 💡 부록: 기타 스크립트 (Maintenance & Study)

`graph_db/` 디렉토리 내의 숫자 번호가 붙은 파일들은 시스템 개발 및 테스트를 위한 보조 스크립트입니다.

*   **100번대 (Study & Basic)**:
    *   `101_neo4j_study.py`: Neo4j 연결 및 기본적인 Cypher 쿼리 실행 학습용.
    *   `102_neo4j_llm_qa.py`: LangChain을 이용한 기초적인 GraphQA 연동 테스트.
*   **200번대 (Prototyping)**:
    *   `201_neo4j_seed_data.py`: 더미 데이터를 활용한 초기 그래프 스키마 설계용.
    *   `202_neo4j_hybrid_rag.py`: 벡터 검색과 그래프 검색을 결합한 하이브리드 RAG 로직 실험용.
*   **400번대 (Performance & Test)**:
    *   `401_complex_query_test.py`: 민원-문서-담당자로 이어지는 다중 홉(Multi-hop) 경로 추적 성능 검증.
    *   `test_api.py`: `api_server_real.py`의 엔드포인트가 정상적으로 응답하는지 확인하는 테스트 도구.

