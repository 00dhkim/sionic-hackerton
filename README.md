# 서울시 청년정책 공문서-민원 통합 GraphRAG 시스템

이 프로젝트는 **서울시 청년수당 공문서**와 **민원 답변 데이터**를 결합하여, 민원 사례로부터 정책적 근거(공문서)와 담당자를 추적할 수 있는 **고도화된 Graph Retrieval-Augmented Generation (GraphRAG)** 시스템입니다.

단순히 텍스트만 찾는 기존 RAG의 한계를 넘어, **벡터 유사도**와 **지식 그래프의 관계망**을 동시에 활용하여 질문에 대한 정확한 출처와 근거를 제시합니다.

---

## 🏗️ 시스템 아키텍처

1.  **지식 그래프 (Knowledge Graph)**:
    *   **노드**: `Document` (공문서), `Complaint` (민원), `Person` (작성자), `Department` (부서).
    *   **관계**: 
        *   `AUTHORED`: 작성자 -> 문서
        *   `BELONGS_TO`: 작성자 -> 부서
        *   `CITES`: 문서 -> 문서 (인용 및 참조 관계)
        *   `RELATED_TO`: 민원 -> 공문서 (벡터 유사도 기반 연결, **Top 5**)

2.  **하이브리드 검색 (Hybrid Retrieval)**:
    *   사용자 질문에 대해 **공문서 본문**과 **민원 본문**을 각각의 벡터 인덱스에서 동시 검색.
    *   검색된 노드로부터 그래프 탐색을 수행하여, 관련 담당자, 부서, 그리고 인용된 근거 문서들까지 확보 (Multi-hop Trace).

---

## 📂 프로젝트 구조 (graph_db/)

| 파일명 | 설명 |
|------|-------------|
| `301_build_real_graph.py` | 공문서 메타데이터(CSV) 및 인용 관계 DB 구축. |
| `303_update_doc_content.py` | 공문서 노드에 MD 본문을 업데이트하고 벡터 인덱스(`document_embedding_index`) 생성. |
| `302_add_complaints_node.py` | 민원 데이터를 추가하고 공문서와 유사도 기반 연결 (**Top 5**). |
| `api_server_real.py` | **최종 API 서버**: FastAPI 기반의 통합 검색 및 Multi-hop 추적 답변 API. |
| `test_api.py` | 서버 기능 검증 및 디버깅용 테스트 스크립트. |
| `101_neo4j_study.py` | Neo4j 기초 조작 학습용 스크립트. |
| `401_complex_query_test.py` | 복합 경로(민원-문서-사람) 추적 성능 테스트 스크립트. |

---

## 🚀 설치 및 서버 실행 방법

### 1. 환경 설정
*   **필수 요구사항**: Python 3.12+, Neo4j DB (Docker 추천), OpenAI API Key.
*   **의존성 설치**:
    ```bash
    cd graph_db
    uv sync
    ```
*   **.env 파일 작성** (`graph_db/.env`):
    ```env
    OPENAI_API_KEY=sk-proj-...
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=testpassword
    ```

### 2. 데이터베이스 구축 (순서 엄수)
최초 1회 실행하여 그래프를 생성하고 벡터 인덱스를 빌드합니다.
```bash
# 1. 공문서 기초 데이터(제목, 인용 관계) 구축
uv run 301_build_real_graph.py

# 2. 공문서 본문(MD 파일) 업데이트 및 벡터 인덱스 생성
uv run 303_update_doc_content.py

# 3. 민원 데이터 추가 및 공문서-민원 유사도 연결 (Top 5)
uv run 302_add_complaints_node.py
```

### 3. API 서버 실행
```bash
# 서버 실행 (기본 포트 8000)
uv run uvicorn api_server_real:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🌐 API 가이드

### 1. 검색 (Search)
*   **URL**: `POST /api/search`
*   **Request Body**:
    ```json
    { "query": "서류 미비로 지급이 중단된 민원의 해결책과 담당 부서는?" }
    ```
*   **Response**:
    ```json
    {
      "answer": "민원 답변에 따르면 ..., 관련 근거 문서는 '[회신] ...'이며 담당자는 청년사업담당관의 OOO 님입니다.",
      "sources": [
        { "type": "Complaint", "title": "...", "id": "106" },
        { "type": "Document", "title": "...", "id": "청년사업담당관-12345" }
      ]
    }
    ```

---

## 📝 주요 트러블슈팅 기록

### APOC 플러그인 의존성 제거
LangChain의 기본 `Neo4jGraph`가 요구하는 APOC 플러그인 없이도 동작하도록 `refresh_schema=False` 옵션과 수동 스키마 주입 방식을 사용하여 안정성을 확보했습니다.

### 데이터 정제 (Data Cleaning)
CSV 데이터 로드 시 포함될 수 있는 `\r` 등의 숨은 공백으로 인한 Cypher 매칭 실패를 방지하기 위해 모든 데이터 삽입 및 조회 단계에 `.strip()` 처리를 적용했습니다.

### 벡터 인덱스 초기화 이슈
`Neo4jVector.from_existing_graph` 사용 시 필수 인자인 `embedding_node_property` 누락 및 인덱스 이름 불일치 문제를 해결하여 서버 시작 시 모든 인덱스가 정상 로드되도록 고도화했습니다.

---
**Sinoic Tech Hackathon - GraphRAG Team**

