# Neo4j GraphRAG 학습 및 프로토타입 프로젝트

이 프로젝트는 **Neo4j**, **LangChain**, **FastAPI**, 그리고 **OpenAI**를 활용하여 **Graph Retrieval-Augmented Generation (GraphRAG)** 시스템을 구축하는 과정을 기록한 프로젝트입니다.

기본적인 그래프 조작부터, 자연어를 Cypher 쿼리로 변환하는 방법, 그리고 벡터 검색과 그래프 탐색을 결합한 **하이브리드 RAG API 서버** 구현까지의 내용을 담고 있습니다.

---

## 📂 프로젝트 구조

| 파일명 | 설명 |
|------|-------------|
| `101_neo4j_study.py` | Neo4j 기초 (노드 생성, 관계 연결, 기초 Cypher 쿼리 실행). |
| `102_neo4j_llm_qa.py` | **Text-to-Cypher**: LLM을 이용해 자연어 질문을 Cypher 쿼리로 변환하여 실행. |
| `201_neo4j_seed_data.py` | **데이터 시딩**: 가상의 IT 기업 'Sinoic Tech'의 인물, 팀, 문서 데이터를 구축. |
| `202_neo4j_hybrid_rag.py` | **Hybrid GraphRAG**: 벡터 검색 + 그래프 탐색을 결합한 프로토타입 스크립트. |
| `api_server.py` | **API 서버**: FastAPI 기반의 GraphRAG 검색 API (운영 환경용). |
| `test_api.py` | **API 테스트**: 서버를 자동으로 띄우고 테스트 요청을 보내는 스크립트. |

---

## 🛠️ 주요 학습 내용 및 에러 해결 (중요!)

### 1. APOC 플러그인 에러 해결 (`Could not use APOC procedures`)
LangChain의 `Neo4jGraph`를 사용할 때 가장 흔히 발생하는 에러입니다.
> `Could not use APOC procedures. Please ensure the APOC plugin is installed...`

**원인**: LangChain은 내부적으로 APOC 플러그인(`apoc.meta.data`)을 사용하여 DB 스키마를 자동으로 분석하려 합니다. 하지만 Docker 환경 등에서 이 플러그인이 없거나 권한이 제한된 경우 에러가 발생합니다.

**✅ 해결 방법 (수동 스키마 주입 패턴)**
플러그인 설치와 씨름하는 대신, 자동 체크를 끄고 **스키마를 직접 정의**해주는 것이 가장 확실한 해결책입니다.

1.  **전용 패키지 사용**: `langchain-neo4j` 패키지를 설치합니다.
2.  **초기화 옵션 조절**:
    ```python
    graph = Neo4jGraph(
        url=..., username=..., password=...,
        enhanced_schema=False,  # APOC 기반 강화 스키마 비활성화
        refresh_schema=False    # 초기화 시 자동 스키마 로드 비활성화
    )
    ```
3.  **스키마 수동 주입**:
    ```python
    graph.schema = """
    Node properties:
    - Document {title: STRING, content: STRING}
    Relationships:
    (:Person)-[:AUTHORED]->(:Document)
    """
    ```

### 2. 하이브리드(Hybrid) RAG 프로세스
단순히 텍스트만 찾는 것이 아니라, 그래프의 구조적 정보를 함께 활용합니다.

1.  **임베딩(Indexing)**: `Document` 노드의 `content` 내용을 벡터화하여 Neo4j에 저장합니다.
2.  **벡터 검색(Retrieval)**: 사용자 질문과 의미적으로 가장 유사한 문서 노드를 찾습니다.
3.  **그래프 확장(Expansion)**: 찾은 문서와 연결된 저자(Author), 언급된 기술(Topic), 소속 팀(Team) 정보를 Cypher로 긁어옵니다.
4.  **최종 답변(Generation)**: "문서 내용 + 그래프에서 가져온 관계 정보"를 LLM에게 전달하여 훨씬 정확하고 풍부한 답변을 생성합니다.

---

## 🌐 API 서버 가이드

FastAPI를 사용하여 구축된 GraphRAG 서버 사용법입니다.

### 1. 서버 실행
```bash
# 개발 모드 (코드 수정 시 자동 재시작)
uv run uvicorn api_server:app --reload

# 운영 모드 (포트 8000)
uv run uvicorn api_server:app --host 0.0.0.0 --port 8000
```

### 2. API 명세 (Specification)

#### 헬스 체크 (Health Check)
- **URL**: `GET /health`
- **Response**:
  ```json
  {
    "status": "ok",
    "neo4j_connected": true
  }
  ```

#### 검색 (Search)
- **URL**: `POST /api/search`
- **Content-Type**: `application/json`
- **Request Body**:
  ```json
  {
    "query": "보안 관련 문서를 쓴 사람은 누구야?"
  }
  ```
- **Response Body**:
  ```json
  {
    "answer": "보안 관련 문서는 Charlie가 작성했습니다. 그는 DevOps 엔지니어입니다.",
    "sources": [
      {
        "title": "Q3 DevOps Strategy",
        "content": "Charlie proposed moving our infrastructure...",
        "graph_context": "Author: Charlie (DevOps Engineer)\nMentions: Cloud Computing"
      }
    ]
  }
  ```

---

## 🚀 전체 실행 순서

### 사전 준비
- Neo4j DB 실행 중 (Docker 등)
- `.env` 파일에 `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` 설정 완료

### 단계별 실행
1.  **데이터 구축**: (기존 데이터를 삭제하고 가상 데이터를 채웁니다)
    ```bash
    uv run 201_neo4j_seed_data.py
    ```
2.  **API 서버 실행**:
    ```bash
    uv run uvicorn api_server:app --reload
    ```
3.  **테스트 요청** (새 터미널):
    ```bash
    curl -X POST http://localhost:8000/api/search \
         -H "Content-Type: application/json" \
         -d '{"query": "Frank는 무엇을 공부하고 있어?"}'
    ```

---

## 📝 Cypher 치트시트 (DB 확인용)

**전체 데이터 시각화:**
```cypher
MATCH (n)-[r]->(m) RETURN n, r, m
```

**임베딩 저장 여부 확인:**
```cypher
MATCH (d:Document) 
RETURN d.title, size(d.embedding) AS vector_dim 
LIMIT 5
```
