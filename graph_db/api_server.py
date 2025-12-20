import os
import contextlib
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()  # Load .env file explicitly

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

# --- Graph Logic ---
def get_expanded_context(doc_title: str) -> str:
    """
    Finds related nodes (Author, Mentions) for a given document title using Cypher.
    """
    if not state.graph:
        return ""
        
    query = """
    MATCH (d:Document {title: $title})
    OPTIONAL MATCH (d)<-[:AUTHORED]-(author:Person)
    OPTIONAL MATCH (d)-[:MENTIONS]->(mentioned)
    RETURN 
        author.name as author_name, 
        author.role as author_role,
        collect(labels(mentioned)[0] + ': ' + mentioned.name) as mentions
    """
    try:
        result = state.graph.query(query, params={"title": doc_title})
        if not result:
            return ""
        
        record = result[0]
        context_str = f"  [Graph Metadata]\n"
        if record['author_name']:
            context_str += f"  - Author: {record['author_name']} ({record['author_role']})\n"
        if record['mentions']:
            context_str += f"  - Mentions: {', '.join(record['mentions'])}\n"
        return context_str
    except Exception as e:
        print(f"Error executing Cypher expansion: {e}")
        return ""

# --- Lifespan Manager (Startup/Shutdown) ---
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- Starting API Server ---")
    
    # 1. Connect to Neo4j
    try:
        print(" > Connecting to Neo4j...")
        state.graph = Neo4jGraph(
            url=NEO4J_URI, 
            username=NEO4J_USER, 
            password=NEO4J_PASSWORD,
            enhanced_schema=False, # Vital for stability
            refresh_schema=False
        )
        # Manual Schema Injection
        state.graph.schema = """
        Node properties:
        - Document {title: STRING, content: STRING}
        - Person {name: STRING, role: STRING}
        Relationships:
        (:Person)-[:AUTHORED]->(:Document)
        (:Document)-[:MENTIONS]->(:Person)
        """
        print(" > Neo4j Connected (Schema Injected)")
        
        # 2. Initialize Vector Index
        print(" > Initializing Vector Index...")
        state.vector_index = Neo4jVector.from_existing_graph(
            embedding=OpenAIEmbeddings(),
            url=NEO4J_URI,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
            index_name="document_embedding_index",
            node_label="Document",
            text_node_properties=["content"],
            embedding_node_property="embedding",
        )
        print(" > Vector Index Ready")
        
    except Exception as e:
        print(f"CRITICAL: Failed to initialize Neo4j connection: {e}")
        # In a real app, you might want to exit here
    
    yield
    
    print("--- Shutting Down API Server ---")
    # Cleanup code if needed

# --- FastAPI App ---
app = FastAPI(title="Sinoic GraphRAG API", lifespan=lifespan)

# --- Pydantic Models ---
class SearchRequest(BaseModel):
    query: str

class SourceDocument(BaseModel):
    title: str
    content: str
    graph_context: str

class SearchResponse(BaseModel):
    answer: str
    sources: List[SourceDocument]

# --- Endpoints ---
@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    if not state.vector_index:
        raise HTTPException(status_code=503, detail="Search service not initialized")

    print(f"Processing query: {request.query}")
    
    # 1. Vector Search (Retrieval)
    # Get top 3 similar documents
    docs = state.vector_index.similarity_search(request.query, k=3)
    
    combined_context = ""
    source_list = []
    
    # 2. Graph Expansion & Context Building
    for doc in docs:
        title = doc.metadata.get('title', 'Unknown')
        content = doc.page_content
        
        # Get extra info from Graph
        graph_info = get_expanded_context(title)
        
        # Build context for LLM
        chunk_context = f"Title: {title}\nContent: {content}\n{graph_info}\n---\n"
        combined_context += chunk_context
        
        # Add to response sources
        source_list.append(SourceDocument(
            title=title,
            content=content,
            graph_context=graph_info.strip()
        ))

    # 3. LLM Generation
    template = """
    You are an intelligent assistant for 'Sinoic Tech'.
    Answer the user's question based ONLY on the provided context.
    The context contains document text and related graph metadata (Authors, Mentions).
    
    Context:
    {context}
    
    Question: {question}
    
    Answer clearly and concisely. Cite the author if possible.
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOpenAI(model="gpt-4o")
    chain = prompt | llm | StrOutputParser()
    
    try:
        answer = chain.invoke({"context": combined_context, "question": request.query})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Generation failed: {e}")

    return SearchResponse(answer=answer, sources=source_list)

@app.get("/health")
def health_check():
    return {"status": "ok", "neo4j_connected": state.graph is not None}
