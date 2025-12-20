import os
import pandas as pd
from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

def update_documents_with_content():
    print("--- 1. Connecting to Neo4j ---")
    graph = Neo4jGraph(
        url=NEO4J_URI, 
        username=NEO4J_USER, 
        password=NEO4J_PASSWORD,
        enhanced_schema=False,
        refresh_schema=False
    )

    # 2. Update Content from MD files
    print("\n--- 2. Reading MD files and Updating Content ---")
    # Get all documents from DB
    docs = graph.query("MATCH (d:Document) RETURN d.index as index, d.title as title")
    
    updates = []
    for d in docs:
        idx = d['index']
        md_path = f"docs/attachments/{idx}_parsed.md"
        
        content = ""
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        
        if content:
            updates.append({"index": idx, "content": content})

    if updates:
        print(f" > Updating {len(updates)} documents with content...")
        graph.query("""
        UNWIND $rows AS row
        MATCH (d:Document {index: row.index})
        SET d.content = row.content
        """, params={"rows": updates})
    else:
        print(" > No MD files found to update.")

    # 3. Re-create Vector Index on 'content'
    print("\n--- 3. Re-creating Vector Index on 'content' ---")
    
    # First, drop existing index
    try:
        graph.query("DROP INDEX real_doc_index")
        print(" > Dropped old index.")
    except:
        pass

    # Create new index using Neo4jVector (this embeds content)
    # Using 'content' property as the text to embed
    vector_index = Neo4jVector.from_existing_graph(
        embedding=OpenAIEmbeddings(),
        url=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASSWORD,
        index_name="real_doc_index",
        node_label="Document",
        text_node_properties=["content"],  # <--- HERE: Indexing Full Content!
        embedding_node_property="embedding",
    )
    print(" > Vector Index Re-created successfully on full content.")

if __name__ == "__main__":
    update_documents_with_content()
