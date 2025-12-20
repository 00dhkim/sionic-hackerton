# 서울시 청년정책 공문서-민원 GraphRAG 시스템

이 프로젝트는 **서울시 청년수당 공문서**와 **민원 답변 데이터**를 결합하여, 민원 사례로부터 정책적 근거(공문서)와 담당자를 추적할 수 있는 **고도화된 Graph Retrieval-Augmented Generation (GraphRAG)** 시스템입니다.

---

## 🏗️ 시스템 아키텍처

1.  **지식 그래프 (Knowledge Graph)**:
    *   **노드**: `Document` (공문서), `Complaint` (민원), `Person` (작성자), `Department` (부서).
    *   **관계**: 
        *   `AUTHORED`: 작성자 -> 문서
        *   `BELONGS_TO`: 작성자 -> 부서
        *   `CITES`: 문서 -> 문서 (인용)
        *   `RELATED_TO`: 민원 -> 공문서 (벡터 유사도 기반 연결, **Top 5**)

2.  **하이브리드 검색 (Hybrid Retrieval)**:
    *   사용자 질문에 대해 **공문서 본문**과 **민원 본문**을 동시에 벡터 검색.
    *   검색된 노드로부터 그래프 탐색을 통해 관련 담당자 및 근거 문서를 확보 (Multi-hop Trace).

---

## 📂 프로젝트 구조

| 파일명 | 설명 |
|------|-------------|
| `301_build_real_graph.py` | 공문서 메타데이터 및 인용 관계 DB 구축. |
| `303_update_doc_content.py` | 공문서 노드에 MD 파일 본문을 업데이트하고 벡터 인덱스 생성. |
| `302_add_complaints_node.py` | 민원 데이터를 추가하고 공문서와 유사도 기반 연결 (Top 5). |
| `api_server_real.py` | **최종 API 서버**: 민원-공문서 통합 검색 및 추적 답변 기능. |
| `test_api.py` | 서버 기능 검증용 테스트 스크립트. |

---

## 🚀 설치 및 서버 실행 방법

### 1. 환경 설정
*   **필수 요구사항**: Python 3.12+, Neo4j DB (Docker 등), OpenAI API Key.
*   **의존성 설치**:
    ```bash
    uv sync
    ```
*   **.env 파일 작성**:
    ```env
    OPENAI_API_KEY=your_key_here
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=testpassword
    ```

### 2. 데이터베이스 구축 (최초 1회)
순서대로 실행하여 그래프를 생성하고 인덱스를 빌드합니다.
```bash
# 1. 공문서 기초 데이터 구축
uv run 301_build_real_graph.py

# 2. 공문서 본문 업데이트 및 벡터 인덱스 생성
uv run 303_update_doc_content.py

# 3. 민원 데이터 추가 및 공문서 연결 (Top 5)
uv run 302_add_complaints_node.py
```

### 3. API 서버 실행
```bash
# 서버 실행 (Port 8000)
uv run uvicorn api_server_real:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🌐 API 사용법

### 검색 엔드포인트
*   **URL**: `POST /api/search`
*   **Payload**:
    ```json
    { "query": "서류 미비로 지급이 중단된 경우의 해결책과 담당자는?" }
    ```
*   **특징**: 질문과 유사한 민원 사례를 찾고, 그 민원과 연결된(RELATED_TO) 실제 공문서와 담당 부서 정보를 결합하여 답변을 생성합니다.

---

## 📝 주요 문제 해결 기록
*   **APOC 이슈**: `refresh_schema=False`와 수동 스키마 주입으로 해결.
*   **데이터 정제**: CSV의 `\r` 등 숨은 공백 제거를 위해 `.strip()` 필수 적용.
*   **추적성 강화**: 단순 1-hop을 넘어 민원-공문서-작성자로 이어지는 Multi-hop 쿼리 최적화.