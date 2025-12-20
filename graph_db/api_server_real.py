import os
import contextlib
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv() 

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# --- Configuration ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

# --- Global State ---
class AppState:
    graph: Optional[Neo4jGraph] = None
    vector_index: Optional[Neo4jVector] = None

state = AppState()

# --- Graph Logic (2-Hop Expansion) ---
def get_expanded_context(doc_title: str) -> str:
    """
    Traverse the graph up to 2 hops to find Author, Department, and Cited Documents.
    """
    if not state.graph:
        return ""
        
    # Optimized Query:
    # 1. Author & Department (1-hop & 2-hop)
    # 2. Other documents by the same author (2-hop) - As per user's logic
    # 3. Cited documents (1-hop) - As per user's logic
    query = """
    MATCH (d:Document {doc_id: $doc_id})
    
    // 1. Author & Department
    OPTIONAL MATCH (d)<-[:AUTHORED]-(author:Person)
    OPTIONAL MATCH (author)-[:BELONGS_TO]->(dept:Department)
    
    // 2. Same Author's other documents (2-hop)
    OPTIONAL MATCH (author)-[:AUTHORED]->(other_doc:Document)
    WHERE other_doc <> d
    
    // 3. Outgoing Citations (This doc cites others)
    OPTIONAL MATCH (d)-[:CITES]->(cited_doc:Document)
    
    // 4. Incoming Citations (Others cite this doc)
    OPTIONAL MATCH (citing_doc:Document)-[:CITES]->(d)
    
    RETURN 
        author.name as author_name, 
        dept.name as dept_name,
        collect(DISTINCT 'Same Author: ' + other_doc.title) as same_author_docs,
        collect(DISTINCT 'Cites: ' + cited_doc.title) as cited_docs,
        collect(DISTINCT 'Cited By: ' + citing_doc.title) as citing_docs
    """
    try:
        print(f"DEBUG: Expanding context for doc_id: {doc_id}")
        result = state.graph.query(query, params={"doc_id": doc_id})
        print(f"DEBUG: Query result: {result}")
        
        if not result:
            return ""
        
        record = result[0]
        context_str = f"  [Metadata & Relations]\n"
        
        # Author & Dept
        if record['author_name']:
            context_str += f"  - Author: {record['author_name']}"
            if record['dept_name']:
                context_str += f" (Dept: {record['dept_name']})"
            context_str += "\n"
            
        # Combine related documents
        related_docs = record['cited_docs'] + record['same_author_docs']
        related_docs = [rd for rd in related_docs if rd and 'null' not in rd]
        
        if related_docs:
            context_str += f"  - Related Docs (via Citations or Author):\n    " + "\n    ".join(related_docs[:6]) + "\n"
            
        return context_str
    except Exception as e:
        print(f"Error executing Cypher expansion: {e}")
        return ""

# --- Lifespan Manager ---
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- Starting Real GraphRAG Server ---")
    
    try:
        # 1. Connect to Neo4j
        print(" > Connecting to Neo4j...")
        state.graph = Neo4jGraph(
            url=NEO4J_URI, 
            username=NEO4J_USER, 
            password=NEO4J_PASSWORD,
            enhanced_schema=False, 
            refresh_schema=False
        )
        
        # Real Schema Injection
        state.graph.schema = """
        Node properties:
        - Document {title: STRING, date: STRING, doc_id: STRING}
        - Person {name: STRING}
        - Department {name: STRING}
        Relationships:
        (:Person)-[:AUTHORED]->(:Document)
        (:Person)-[:BELONGS_TO]->(:Department)
        (:Document)-[:CITES]->(:Document)
        """
        print(" > Neo4j Connected & Schema Injected")
        
        # 2. Initialize Vector Index
        # Since we don't have full body content in DB yet, we use 'title' for embedding.
        # Ideally, we should have a 'content' field populated from the parsed markdown files.
        print(" > Initializing Vector Index on 'title'...")
        state.vector_index = Neo4jVector.from_existing_graph(
            embedding=OpenAIEmbeddings(),
            url=NEO4J_URI,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
            index_name="real_doc_index",
            node_label="Document",
            text_node_properties=["title"], # Using Title as the search key for now
            embedding_node_property="embedding",
        )
        print(" > Vector Index Ready")
        
    except Exception as e:
        print(f"CRITICAL: Initialization failed: {e}")
    
    yield
    print("--- Shutting Down Server ---")

# --- FastAPI App ---
app = FastAPI(title="Seoul Youth Policy GraphRAG", lifespan=lifespan)

class SearchRequest(BaseModel):
    query: str

class SourceDocument(BaseModel):
    title: str
    doc_id: str
    graph_context: str

class SearchResponse(BaseModel):
    answer: str
    sources: List[SourceDocument]

@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    if not state.vector_index:
        raise HTTPException(status_code=503, detail="Service not ready")

    print(f"Processing query: {request.query}")
    
    # 1. Vector Retrieval (Increased to k=5)
    docs = state.vector_index.similarity_search(request.query, k=5)
    
    combined_context = ""
    source_list = []
    
    # 2. Graph Expansion (2-Hop)
    for doc in docs:
        title = doc.page_content 
        # Extract and clean doc_id
        doc_id = str(doc.metadata.get('doc_id', 'Unknown')).strip()
        
        # Get expanded context using cleaned DOC_ID
        graph_info = get_expanded_context(doc_id)
        
        # Build Context
        chunk = f"Document: {title}\nDoc ID: {doc_id}\n{graph_info}\n---\n"
        combined_context += chunk
        
        source_list.append(SourceDocument(
            title=title,
            doc_id=doc_id,
            graph_context=graph_info.strip()
        ))

    # 3. Generation
    template = """
    You are an expert on Seoul Youth Policy documents.
    Answer the user's question using the provided context.
    
    The context includes:
    - Document Titles
    - Authors and their Departments
    - Related Documents (Citations)
    
    Context:
    {context}
    
    Question: {question}
    
    Answer in Korean. Be specific about document names and authors.
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOpenAI(model="gpt-4o")
    chain = prompt | llm | StrOutputParser()
    
    try:
        answer = chain.invoke({"context": combined_context, "question": request.query})
    except Exception as e:
        answer = f"Error generating answer: {e}"

    return SearchResponse(answer=answer, sources=source_list)

@app.get("/health")
def health():
    return {"status": "ok"}
