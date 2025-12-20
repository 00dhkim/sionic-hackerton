import os
import contextlib
from pathlib import Path
from typing import Dict, Optional, Union
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# --- Configuration ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")
FRONTEND_DIR = Path(__file__).parent / "frontend"

# --- Global State ---
class AppState:
    graph: Optional[Neo4jGraph] = None
    doc_vector: Optional[Neo4jVector] = None
    complaint_vector: Optional[Neo4jVector] = None

state = AppState()

# --- Helpers ---
def build_node_key(label: str, properties: Dict[str, Union[str, int, None]]) -> str:
    if label == "Document":
        return f"Document:{properties.get('doc_id') or properties.get('docId') or properties.get('id') or properties.get('node_key')}"
    if label == "Complaint":
        idx = properties.get("complaint_index") or properties.get("index")
        return f"Complaint:{idx}"
    if label == "Person":
        return f"Person:{properties.get('name') or properties.get('title')}"
    if label == "Department":
        return f"Department:{properties.get('name') or properties.get('title')}"
    return f"{label}:{properties.get('id') or properties.get('node_key')}"


def get_trace_context(node_id: Union[int, str], label: str) -> str:
    """
    Traverse the graph based on the starting node type.
    """
    if not state.graph:
        return ""

    if label == "Complaint":
        # Complaint -> Related Docs -> Authors
        query = """
        MATCH (c:Complaint {index: $id})
        OPTIONAL MATCH (c)-[r:RELATED_TO]->(d:Document)
        OPTIONAL MATCH (d)<-[:AUTHORED]-(p:Person)
        RETURN 
            d.title as doc_title,
            d.doc_id as doc_id,
            p.name as author_name,
            r.score as sim_score
        ORDER BY sim_score DESC LIMIT 5
        """
        result = state.graph.query(query, params={"id": node_id})
        context = "  [Related Public Documents & Authors]\n"
        for row in result:
            if row['doc_title']:
                context += f"  - {row['doc_title']} (ID: {row['doc_id']}) / 담당자: {row['author_name']}\n"
        return context

    elif label == "Document":
        # Document -> Author -> Other Docs & Citations
        query = """
        MATCH (d:Document {doc_id: $id})
        OPTIONAL MATCH (d)<-[:AUTHORED]-(p:Person)-[:BELONGS_TO]->(dep:Department)
        OPTIONAL MATCH (d)-[:CITES]->(cited:Document)
        RETURN 
            p.name as author, dep.name as dept,
            collect(DISTINCT cited.title) as citations
        """
        result = state.graph.query(query, params={"id": node_id})
        if not result:
            return ""
        row = result[0]
        context = f"  [Metadata]\n  - Author: {row['author']} ({row['dept']})\n"
        if row['citations']:
            context += f"  - Citations: {', '.join(row['citations'][:3])}\n"
        return context

    return ""


# --- Lifespan Manager ---
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- Starting Advanced GraphRAG Server ---")
    try:
        state.graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USER, password=NEO4J_PASSWORD, refresh_schema=False)

        # Initialize Vectors
        embeddings = OpenAIEmbeddings()
        state.doc_vector = Neo4jVector.from_existing_graph(
            embeddings, url=NEO4J_URI, username=NEO4J_USER, password=NEO4J_PASSWORD,
            index_name="document_embedding_index", node_label="Document", text_node_properties=["content"]
        )
        state.complaint_vector = Neo4jVector.from_existing_graph(
            embeddings, url=NEO4J_URI, username=NEO4J_USER, password=NEO4J_PASSWORD,
            index_name="complaint_index", node_label="Complaint", text_node_properties=["content"]
        )
        print(" > Vectors & Graph Ready.")
    except Exception as e:
        print(f"Init Error: {e}")
    yield


app = FastAPI(title="Seoul Youth Policy Advanced RAG", lifespan=lifespan)
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="ui")


class SearchRequest(BaseModel):
    query: str


@app.post("/api/search")
async def search(request: SearchRequest):
    if not (state.doc_vector and state.complaint_vector):
        raise HTTPException(status_code=503, detail="Search indexes are not ready yet.")

    c_docs = state.complaint_vector.similarity_search(request.query, k=2)
    d_docs = state.doc_vector.similarity_search(request.query, k=2)

    combined_context = ""
    sources = []

    # Process Complaints
    for doc in c_docs:
        idx = doc.metadata['index']
        graph_info = get_trace_context(idx, "Complaint")
        combined_context += f"[Complaint]: {doc.page_content[:300]}\n{graph_info}\n---\n"
        sources.append({
            "type": "Complaint",
            "title": doc.page_content[:50],
            "id": str(idx),
            "nodeKey": build_node_key("Complaint", {"index": idx})
        })

    # Process Documents
    for doc in d_docs:
        doc_id = doc.metadata['doc_id']
        graph_info = get_trace_context(doc_id, "Document")
        combined_context += f"[Document]: {doc.metadata['title']}\nContent: {doc.page_content[:300]}\n{graph_info}\n---\n"
        sources.append({
            "type": "Document",
            "title": doc.metadata['title'],
            "id": doc_id,
            "nodeKey": build_node_key("Document", {"doc_id": doc_id})
        })

    # Generate Answer
    template = """
    당신은 서울시 청년정책 전문가입니다. 제공된 민원(Complaint)과 공문서(Document) 정보를 바탕으로 답변하세요.
    질문과 관련된 민원 사례가 있다면 언급하고, 그 해결 근거가 되는 공문서와 담당자 정보를 반드시 포함하세요.
    
    Context:
    {context}
    
    Question: {question}
    """
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOpenAI(model="gpt-4o")
    answer = (prompt | llm | StrOutputParser()).invoke({"context": combined_context, "question": request.query})

    return {"answer": answer, "sources": sources, "context": combined_context}


@app.get("/api/graph")
async def graph_snapshot(node_limit: int = 400):
    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph is not ready yet.")

    node_query = """
    MATCH (n)
    WITH labels(n)[0] AS label, n
    RETURN 
        label AS label,
        CASE 
            WHEN label = 'Document' THEN 'Document:' + coalesce(n.doc_id, toString(id(n)))
            WHEN label = 'Complaint' THEN 'Complaint:' + coalesce(toString(n.index), toString(id(n)))
            WHEN label = 'Person' THEN 'Person:' + coalesce(n.name, toString(id(n)))
            WHEN label = 'Department' THEN 'Department:' + coalesce(n.name, toString(id(n)))
            ELSE label + ':' + toString(id(n))
        END AS node_key,
        coalesce(n.title, n.name, n.doc_id, toString(n.index), 'Untitled') AS title,
        n.doc_id AS doc_id,
        n.index AS complaint_index,
        n.name AS name,
        CASE 
            WHEN label = 'Document' THEN substring(coalesce(n.content, ''), 0, 160)
            WHEN label = 'Complaint' THEN substring(coalesce(n.content, ''), 0, 160)
            ELSE ''
        END AS preview
    LIMIT $node_limit
    """
    node_rows = state.graph.query(node_query, params={"node_limit": node_limit})

    nodes = [
        {
            "id": row["node_key"],
            "label": row["label"],
            "title": row["title"],
            "docId": row.get("doc_id"),
            "complaintIndex": row.get("complaint_index"),
            "name": row.get("name"),
            "preview": row.get("preview", "")
        }
        for row in node_rows
    ]
    node_keys = {node["id"] for node in nodes}

    edge_query = """
    MATCH (a)-[r]->(b)
    WITH labels(a)[0] AS source_label, labels(b)[0] AS target_label, a, b, type(r) AS rel_type
    RETURN 
        rel_type AS type,
        CASE 
            WHEN source_label = 'Document' THEN 'Document:' + coalesce(a.doc_id, toString(id(a)))
            WHEN source_label = 'Complaint' THEN 'Complaint:' + coalesce(toString(a.index), toString(id(a)))
            WHEN source_label = 'Person' THEN 'Person:' + coalesce(a.name, toString(id(a)))
            WHEN source_label = 'Department' THEN 'Department:' + coalesce(a.name, toString(id(a)))
            ELSE source_label + ':' + toString(id(a))
        END AS source_key,
        CASE 
            WHEN target_label = 'Document' THEN 'Document:' + coalesce(b.doc_id, toString(id(b)))
            WHEN target_label = 'Complaint' THEN 'Complaint:' + coalesce(toString(b.index), toString(id(b)))
            WHEN target_label = 'Person' THEN 'Person:' + coalesce(b.name, toString(id(b)))
            WHEN target_label = 'Department' THEN 'Department:' + coalesce(b.name, toString(id(b)))
            ELSE target_label + ':' + toString(id(b))
        END AS target_key
    """
    edge_rows = state.graph.query(edge_query)

    edges = [
        {"from": row["source_key"], "to": row["target_key"], "type": row["type"]}
        for row in edge_rows
        if row["source_key"] in node_keys and row["target_key"] in node_keys
    ]

    return {"nodes": nodes, "edges": edges}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    if FRONTEND_DIR.exists():
        return FileResponse(FRONTEND_DIR / "index.html")
    return {"message": "GraphRAG API is running"}
