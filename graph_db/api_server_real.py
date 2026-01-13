import os
import sys
import contextlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Union
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from hyde_utils import generate_hypothetical_document

# --- Configuration ---
# Look for .env in the current directory OR one level up (project root)
# In Vercel, env vars are injected directly, so we don't strictly need .env file
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv() # Fallback to default behavior

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

# --- Global State ---
class AppState:
    graph: Optional[Neo4jGraph] = None
    doc_vector: Optional[Neo4jVector] = None
    complaint_vector: Optional[Neo4jVector] = None

state = AppState()
STATIC_DIR = BASE_DIR / "static"

# --- Graph Logic ---
def get_complaint_context(node_id: Union[int, str]) -> Dict:
    """
    Traverse Complaint -> Related Docs -> Authors for UI context and graph highlighting.
    """
    if not state.graph:
        return {"context_text": "", "neo4j_id": None, "related_documents": []}

    query = """
    MATCH (c:Complaint {index: $id})
    OPTIONAL MATCH (c)-[r:RELATED_TO]->(d:Document)
    OPTIONAL MATCH (d)<-[:AUTHORED]-(p:Person)
    RETURN 
        id(c) as complaint_node_id,
        d.title as doc_title,
        d.doc_id as doc_id,
        id(d) as doc_node_id,
        p.name as author_name,
        id(p) as author_node_id,
        r.score as sim_score
    ORDER BY sim_score DESC LIMIT 5
    """
    result = state.graph.query(query, params={"id": node_id})
    context_lines = ["  [Related Public Documents & Authors]"]
    related_docs = []

    complaint_node_id = None
    for row in result:
        if complaint_node_id is None:
            complaint_node_id = row.get("complaint_node_id")
        if row.get("doc_title"):
            related_docs.append(
                {
                    "doc_id": row.get("doc_id"),
                    "title": row.get("doc_title"),
                    "neo4j_id": row.get("doc_node_id"),
                    "author": row.get("author_name"),
                    "author_node_id": row.get("author_node_id"),
                    "similarity": row.get("sim_score"),
                }
            )
            context_lines.append(
                f"  - {row.get('doc_title')} (ID: {row.get('doc_id')}) / 담당자: {row.get('author_name')}"
            )

    return {
        "context_text": "\n".join(context_lines) if len(context_lines) > 1 else "",
        "neo4j_id": complaint_node_id,
        "related_documents": related_docs,
    }


def get_document_context(node_id: Union[int, str]) -> Dict:
    """
    Traverse Document -> Author/Department -> Citations for UI context and graph highlighting.
    """
    if not state.graph:
        return {"context_text": "", "neo4j_id": None, "metadata": {}}

    query = """
    MATCH (d:Document {doc_id: $id})
    OPTIONAL MATCH (d)<-[:AUTHORED]-(p:Person)-[:BELONGS_TO]->(dep:Department)
    OPTIONAL MATCH (d)-[:CITES]->(cited:Document)
    RETURN 
        id(d) as doc_node_id,
        p.name as author, id(p) as author_node_id,
        dep.name as dept, id(dep) as dept_node_id,
        collect(DISTINCT {title: cited.title, doc_id: cited.doc_id, neo4j_id: id(cited)}) as citations
    """
    result = state.graph.query(query, params={"id": node_id})
    if not result:
        return {"context_text": "", "neo4j_id": None, "metadata": {}}

    row = result[0]
    metadata = {
        "author": row.get("author"),
        "author_node_id": row.get("author_node_id"),
        "department": row.get("dept"),
        "department_node_id": row.get("dept_node_id"),
        "citations": row.get("citations") or [],
    }

    context_lines = ["  [Metadata]"]
    if metadata["author"]:
        dept_text = f" ({metadata['department']})" if metadata["department"] else ""
        context_lines.append(f"  - Author: {metadata['author']}{dept_text}")
    if metadata["citations"]:
        cited_titles = [c["title"] for c in metadata["citations"] if c.get("title")]
        if cited_titles:
            context_lines.append(f"  - Citations: {', '.join(cited_titles[:3])}")

    return {
        "context_text": "\n".join(context_lines) if len(context_lines) > 1 else "",
        "neo4j_id": row.get("doc_node_id"),
        "metadata": metadata,
    }

# --- Lifespan Manager ---
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- Starting Advanced GraphRAG Server ---")
    try:
        print(" > Connecting to Neo4j...")
        state.graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USER, password=NEO4J_PASSWORD, refresh_schema=False)
        
        embeddings = OpenAIEmbeddings()
        
        # Initialize Document Vector
        print(" > Loading Document Vector Index...")
        try:
            state.doc_vector = Neo4jVector.from_existing_graph(
                embeddings, 
                url=NEO4J_URI, 
                username=NEO4J_USER, 
                password=NEO4J_PASSWORD,
                index_name="document_embedding_index", 
                node_label="Document", 
                text_node_properties=["content"],
                embedding_node_property="embedding"  # Added
            )
            print("   - Document Index Ready.")
        except Exception as e:
            print(f"   - FAILED to load Document Index: {e}")

        # Initialize Complaint Vector
        print(" > Loading Complaint Vector Index...")
        try:
            state.complaint_vector = Neo4jVector.from_existing_graph(
                embeddings, 
                url=NEO4J_URI, 
                username=NEO4J_USER, 
                password=NEO4J_PASSWORD,
                index_name="complaint_index", 
                node_label="Complaint", 
                text_node_properties=["content"],
                embedding_node_property="embedding"  # Added
            )
            print("   - Complaint Index Ready.")
        except Exception as e:
            print(f"   - FAILED to load Complaint Index: {e}")

        if state.doc_vector and state.complaint_vector:
            print(" > [SUCCESS] All Vectors & Graph Ready.")
        else:
            print(" > [WARNING] Some indexes failed to load. Search might be unavailable.")

    except Exception as e:
        print(f"CRITICAL Init Error: {e}")
    yield

app = FastAPI(title="Seoul Youth Policy Advanced RAG", lifespan=lifespan)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """
    Serve the interactive Graph RAG frontend when available.
    """
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Graph RAG API is running.</h1>")

class SearchRequest(BaseModel):
    query: str
    use_hyde: bool = False

@app.post("/api/search")
async def search(request: SearchRequest):
    # Sanity check: Ensure vectors are initialized
    if not state.complaint_vector or not state.doc_vector:
        raise HTTPException(
            status_code=503,
            detail="Search service is still initializing or failed to load vector indexes. Please check server logs."
        )

    # Determine search query based on HyDE setting
    search_query = request.query
    hypothetical_doc = None
    
    if request.use_hyde:
        # Generate hypothetical document for HyDE
        try:
            hypothetical_doc = generate_hypothetical_document(request.query)
            search_query = hypothetical_doc
            print(f"[HyDE] Generated hypothetical document for query: {request.query[:50]}...")
        except Exception as e:
            print(f"[HyDE] Failed to generate hypothetical document: {e}. Using original query.")

    # 1. Search both indexes
    try:
        c_docs = state.complaint_vector.similarity_search(search_query, k=2)
        d_docs = state.doc_vector.similarity_search(search_query, k=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector search failed: {e}")
    
    combined_context = ""
    sources = []
    contexts = {"complaints": [], "documents": []}
    highlighted_nodes: Set[int] = set()
    
    # Process Complaints
    for doc in c_docs:
        idx = doc.metadata["index"]
        context_data = get_complaint_context(idx)
        complaint_snippet = doc.page_content[:300]
        if context_data["neo4j_id"]:
            highlighted_nodes.add(context_data["neo4j_id"])
        for related in context_data["related_documents"]:
            if related.get("neo4j_id"):
                highlighted_nodes.add(related["neo4j_id"])
            if related.get("author_node_id"):
                highlighted_nodes.add(related["author_node_id"])

        contexts["complaints"].append(
            {
                "id": idx,
                "neo4j_id": context_data["neo4j_id"],
                "snippet": complaint_snippet,
                "related_documents": context_data["related_documents"],
            }
        )
        combined_context += f"[Complaint]: {complaint_snippet}\n{context_data['context_text']}\n---\n"
        sources.append({"type": "Complaint", "title": complaint_snippet, "id": str(idx)})
        
    # Process Documents
    for doc in d_docs:
        doc_id = doc.metadata["doc_id"]
        doc_title = doc.metadata["title"]
        context_data = get_document_context(doc_id)
        doc_snippet = doc.page_content[:300]

        if context_data["neo4j_id"]:
            highlighted_nodes.add(context_data["neo4j_id"])
        meta = context_data["metadata"]
        for node_key in ("author_node_id", "department_node_id"):
            if meta.get(node_key):
                highlighted_nodes.add(meta[node_key])
        for citation in meta.get("citations", []):
            if citation.get("neo4j_id"):
                highlighted_nodes.add(citation["neo4j_id"])

        contexts["documents"].append(
            {
                "id": doc_id,
                "neo4j_id": context_data["neo4j_id"],
                "title": doc_title,
                "snippet": doc_snippet,
                "metadata": meta,
            }
        )
        combined_context += f"[Document]: {doc_title}\nContent: {doc_snippet}\n{context_data['context_text']}\n---\n"
        sources.append({"type": "Document", "title": doc_title, "id": doc_id})

    # 2. Generate Answer
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
    
    response_data = {
        "answer": answer,
        "sources": sources,
        "context": contexts,
        "highlighted_nodes": list(highlighted_nodes),
        "search_method": "HyDE" if request.use_hyde else "Standard",
        "hypothetical_document": hypothetical_doc if request.use_hyde else None,
    }

    # A/B Test: If use_hyde is True, also run standard search for comparison
    if request.use_hyde:
        try:
            # Run standard search
            c_docs_std = state.complaint_vector.similarity_search(request.query, k=2)
            d_docs_std = state.doc_vector.similarity_search(request.query, k=2)
            
            # Build standard search context and answer
            std_combined_context = ""
            std_sources = []
            std_contexts = {"complaints": [], "documents": []}
            
            for doc in c_docs_std:
                idx = doc.metadata["index"]
                std_contexts["complaints"].append({"id": idx, "snippet": doc.page_content[:500]})
                std_combined_context += f"[Complaint]: {doc.page_content[:500]}\n---\n"
                std_sources.append({"type": "Complaint", "title": doc.page_content[:150], "id": str(idx)})
            
            for doc in d_docs_std:
                doc_id = doc.metadata.get("doc_id")
                doc_title = doc.metadata.get("title")
                std_contexts["documents"].append({"id": doc_id, "title": doc_title, "snippet": doc.page_content[:500]})
                std_combined_context += f"[Document]: {doc_title}\nContent: {doc.page_content[:500]}\n---\n"
                std_sources.append({"type": "Document", "title": doc_title or doc.page_content[:150], "id": doc_id})
            
            # Generate standard answer
            std_answer = (prompt | llm | StrOutputParser()).invoke({"context": std_combined_context, "question": request.query})
            
            response_data["standard_answer"] = std_answer
            response_data["standard_search_sources"] = std_sources
            response_data["standard_context"] = std_contexts
        except Exception as e:
            print(f"[A/B Test] Failed to run standard search for comparison: {e}")

    return response_data

@app.get("/api/graph/overview")
async def graph_overview(limit: int = 300):
    """
    Fetch a simplified snapshot of the knowledge graph for UI visualization.
    """
    if not state.graph:
        raise HTTPException(status_code=503, detail="Graph connection not initialized.")

    nodes = state.graph.query(
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['Document', 'Complaint', 'Person', 'Department'])
        RETURN id(n) as id, labels(n) as labels, n.doc_id as doc_id, n.index as complaint_index,
               n.title as title, n.name as name
        LIMIT $limit
        """,
        params={"limit": limit},
    )
    node_ids = [row["id"] for row in nodes]

    edges: List[Dict] = []
    if node_ids:
        edges = state.graph.query(
            """
            MATCH (n)-[r]->(m)
            WHERE id(n) IN $ids AND id(m) IN $ids
            RETURN id(n) as source, id(m) as target, type(r) as type
            LIMIT 400
            """,
            params={"ids": node_ids},
        )

    node_payload = []
    for row in nodes:
        label = row["labels"][0] if row.get("labels") else "Node"
        display_name = row.get("title") or row.get("name") or row.get("doc_id") or row.get("complaint_index")
        node_payload.append(
            {
                "id": row["id"],
                "labels": row.get("labels", []),
                "display": display_name,
                "doc_id": row.get("doc_id"),
                "complaint_index": row.get("complaint_index"),
                "title": row.get("title"),
                "name": row.get("name"),
                "primary_label": label,
            }
        )

    return {"nodes": node_payload, "edges": edges}

@app.get("/health")
def health(): return {"status": "ok"}
