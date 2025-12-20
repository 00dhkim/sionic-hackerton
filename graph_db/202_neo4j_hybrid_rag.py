import os
from typing import List, Dict
from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 1. Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

# 2. Connection (APOC Bypass)
try:
    graph = Neo4jGraph(
        url=NEO4J_URI, 
        username=NEO4J_USER, 
        password=NEO4J_PASSWORD,
        enhanced_schema=False,
        refresh_schema=False
    )
    
    # Manual Schema Definition (Important for understanding context)
    graph.schema = """
    Node properties:
    - Document {title: STRING, content: STRING}
    - Person {name: STRING, role: STRING}
    - Topic {name: STRING}
    - Team {name: STRING}
    
    Relationships:
    (:Person)-[:AUTHORED]->(:Document)
    (:Document)-[:MENTIONS]->(:Person)
    (:Document)-[:MENTIONS]->(:Topic)
    (:Document)-[:MENTIONS]->(:Team)
    """
    print(" > Neo4j Connected & Schema Manually Loaded")
except Exception as e:
    print(f"Connection Error: {e}")
    exit(1)

# 3. Vector Index Setup
# This will calculate embeddings for all 'Document' nodes using their 'content' property
print(" > Initializing Vector Index (This might take a moment)...")
vector_index = Neo4jVector.from_existing_graph(
    embedding=OpenAIEmbeddings(),
    url=NEO4J_URI,
    username=NEO4J_USER,
    password=NEO4J_PASSWORD,
    index_name="document_embedding_index",
    node_label="Document",
    text_node_properties=["content"],  # The text to embed
    embedding_node_property="embedding", # Where to store the vector
)
print(" > Vector Index Ready.")

# 4. Context Expansion Function
def get_expanded_context(doc_title: str) -> str:
    """
    Given a document title, find related nodes (Author, Mentions, etc.) using Cypher.
    """
    query = """
    MATCH (d:Document {title: $title})
    OPTIONAL MATCH (d)<-[:AUTHORED]-(author:Person)
    OPTIONAL MATCH (d)-[:MENTIONS]->(mentioned)
    RETURN 
        d.title as title, 
        author.name as author_name, 
        author.role as author_role,
        collect(labels(mentioned)[0] + ': ' + mentioned.name) as mentions
    """
    result = graph.query(query, params={"title": doc_title})
    
    if not result:
        return ""
    
    record = result[0]
    context_str = "\n  [Related Graph Data]\n"
    context_str += f"  - Author: {record['author_name']} ({record['author_role']})\n"
    if record['mentions']:
        context_str += f"  - Mentions: {', '.join(record['mentions'])}\n"
    
    return context_str

# 5. Hybrid RAG Chain
def hybrid_rag_chat(question: str):
    print(f"\n[Question]: {question}")
    
    # Step A: Vector Search (Retrieval)
    # Get top 2 most similar documents
    search_results = vector_index.similarity_search(question, k=2)
    
    combined_context = ""
    
    print(" > Retrieved Documents:")
    for i, doc in enumerate(search_results):
        # Neo4jVector returns 'content' in page_content and other props in metadata
        title = doc.metadata.get('title', 'Unknown')
        content = doc.page_content
        
        print(f"   {i+1}. {title}")
        
        # Step B: Graph Expansion
        graph_context = get_expanded_context(title)
        
        # Combine Text + Graph Context
        combined_context += f"Document Title: {title}\nContent: {content}\n{graph_context}\n---\n"

    # Step C: Generation (LLM)
    template = """
    You are an intelligent assistant for 'Sinoic Tech'.
    Answer the user's question using the provided context. 
    The context includes document text and structured graph relationships (Authors, Mentions).
    
    Context:
    {context}
    
    Question: {question}
    
    Answer clearly and specifically. Mention who authored the relevant documents if known.
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOpenAI(model="gpt-4o") # Using a smart model
    chain = prompt | llm | StrOutputParser()
    
    response = chain.invoke({"context": combined_context, "question": question})
    print(f"\n[Answer]:\n{response}")

# 6. Run Examples
if __name__ == "__main__":
    # Question 1: Requires finding a doc about 'infrastructure' and knowing who wrote it (Author)
    hybrid_rag_chat("우리 인프라 전략이랑 보안 관련 내용은 누가 담당했어?")
    
    # Question 2: Requires connecting 'Frank' (Intern) to what he is studying (from Document content)
    hybrid_rag_chat("Frank는 인턴 기간 동안 뭘 공부할 예정이야?")
