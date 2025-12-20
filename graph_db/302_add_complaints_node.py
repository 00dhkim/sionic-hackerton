import os
import pandas as pd
from langchain_neo4j import Neo4jGraph
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

def add_complaints():
    print("--- 1. Loading Data ---")
    try:
        df = pd.read_csv("../data/seoul_youth_allowance_complaints_updated.csv")
        print(f" > Found {len(df)} complaints.")
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return

    print("\n--- 2. Connecting to Neo4j ---")
    graph = Neo4jGraph(
        url=NEO4J_URI, 
        username=NEO4J_USER, 
        password=NEO4J_PASSWORD,
        enhanced_schema=False,
        refresh_schema=False
    )
    embeddings = OpenAIEmbeddings()

    # 3. Process each complaint
    print("\n--- 3. Processing Complaints & Linking ---")
    
    complaint_nodes = []
    
    for _, row in df.iterrows():
        idx = row['Index']
        title = str(row['Document Name']).strip()
        date = str(row['Date']).strip() if pd.notna(row['Date']) else ""
        
        # Read content from MD file
        md_path = f"../docs/attachments_complaints/{idx}_parsed.md"
        content = ""
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        
        # Fallback if MD is empty
        full_text = f"제목: {title}\n내용: {content}" if content else title
        
        # Generate Embedding
        vector = embeddings.embed_query(full_text)
        
        complaint_nodes.append({
            "index": int(idx),
            "title": title,
            "date": date,
            "content": content,
            "embedding": vector
        })
        
        if len(complaint_nodes) % 10 == 0:
            print(f" > Processed {len(complaint_nodes)} complaints...")

    # 4. Insert Complaints & Create Vector Index for Complaints
    print(f"\n > Inserting {len(complaint_nodes)} Complaint nodes...")
    
    query_insert = """
    UNWIND $rows AS row
    MERGE (c:Complaint {index: row.index})
    SET c.title = row.title,
        c.date = row.date,
        c.content = row.content,
        c.embedding = row.embedding
    """
    graph.query(query_insert, params={"rows": complaint_nodes})

    # 5. Link to Similar Documents
    print("\n--- 4. Linking Complaints to Documents (Similarity Search) ---")
    
    # Using the correct index name: 'document_embedding_index'
    # Changed from 1 to 5
    query_link = """
    MATCH (c:Complaint)
    WHERE c.embedding IS NOT NULL
    CALL db.index.vector.queryNodes('document_embedding_index', 5, c.embedding) 
    YIELD node AS sim_doc, score
    WHERE score > 0.5 
    MERGE (c)-[r:RELATED_TO]->(sim_doc)
    SET r.score = score
    RETURN count(r) as links_created
    """
    
    try:
        result = graph.query(query_link)
        print(f" > Created relationships: {result}")
        
        # Check some examples
        print("\n--- Sample Links Created ---")
        samples = graph.query("""
        MATCH (c:Complaint)-[r:RELATED_TO]->(d:Document)
        RETURN c.title as Complaint, d.title as Document, r.score as Score
        LIMIT 5
        """)
        for s in samples:
            print(f" [LINK] {s['Complaint'][:30]}... \n        -> {s['Document'][:30]}... (Score: {s['Score']:.4f})")
    except Exception as e:
        print(f"Error linking nodes: {e}")
        print("Hint: Check if 'real_doc_index' exists and tracks embeddings.")

    print("\n--- Done ---")

if __name__ == "__main__":
    add_complaints()
