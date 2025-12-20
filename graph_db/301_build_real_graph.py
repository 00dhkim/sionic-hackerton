import os
import pandas as pd
from langchain_neo4j import Neo4jGraph

# 1. Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

def build_graph():
    print("--- 1. Loading Data ---")
    # Load CSVs
    try:
        df_docs = pd.read_csv("../data/seoul_youth_allowance_others_with_docnum.csv")
        df_cites = pd.read_csv("../data/citation_relations.csv")
        print(f" > Documents: {len(df_docs)} rows")
        print(f" > Citations: {len(df_cites)} rows")
    except Exception as e:
        print(f"Error loading CSV files: {e}")
        return

    print("\n--- 2. Connecting to Neo4j ---")
    try:
        graph = Neo4jGraph(
            url=NEO4J_URI, 
            username=NEO4J_USER, 
            password=NEO4J_PASSWORD,
            enhanced_schema=False,
            refresh_schema=False
        )
        print(" > Connected successfully.")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # 3. Clean DB
    print("\n--- 3. Cleaning Database ---")
    graph.query("MATCH (n) DETACH DELETE n")
    
    # Drop existing vector index to force rebuild
    try:
        graph.query("DROP INDEX real_doc_index")
        print(" > Dropped old vector index 'real_doc_index'")
    except:
        pass # Index might not exist
    
    # 4. Create Indexes (Optional but recommended for performance)
    print("\n--- 4. Creating Indexes ---")
    try:
        graph.query("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE")
        graph.query("CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.index)")
        graph.query("CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.name)")
        graph.query("CREATE INDEX IF NOT EXISTS FOR (dep:Department) ON (dep.name)")
    except Exception as e:
        print(f"Index creation warning (might already exist): {e}")

    # 5. Insert Nodes (Document, Person, Department)
    print("\n--- 5. Creating Nodes & Basic Relationships ---")
    
    # We will iterate row by row or use UNWIND for bulk insert. 
    # For < 1000 rows, iteration is fine, but UNWIND is cleaner.
    
    doc_data = df_docs.to_dict('records')
    
    # Pre-process data (handle NaNs, etc.)
    cleaned_data = []
    for row in doc_data:
        cleaned_row = {
            "index": int(row['Index']),
            "title": str(row['Document Name']).strip() if pd.notna(row['Document Name']) else "",
            "doc_id": str(row['Doc_Number']).strip() if pd.notna(row['Doc_Number']) else f"UNKNOWN-{row['Index']}",
            "date": str(row['Date']).strip() if pd.notna(row['Date']) else "",
            "author": str(row['Author']).strip() if pd.notna(row['Author']) else "Unknown",
            "department": str(row['Department']).strip() if pd.notna(row['Department']) else "Unknown",
            "url": str(row['URL']).strip() if pd.notna(row['URL']) else ""
        }
        cleaned_data.append(cleaned_row)

    # Bulk Insert Query
    query_create_nodes = """
    UNWIND $rows AS row
    
    // 1. Create Document
    MERGE (d:Document {index: row.index})
    SET d.title = row.title,
        d.doc_id = row.doc_id,
        d.date = row.date,
        d.url = row.url
    
    // 2. Create Author
    MERGE (p:Person {name: row.author})
    
    // 3. Create Department
    MERGE (dep:Department {name: row.department})
    
    // 4. Create Relationships
    MERGE (p)-[:AUTHORED]->(d)
    MERGE (p)-[:BELONGS_TO]->(dep)
    """
    
    graph.query(query_create_nodes, params={"rows": cleaned_data})
    print(f" > Inserted {len(cleaned_data)} documents and related entities.")

    # 6. Insert Citation Relationships
    print("\n--- 6. Creating Citation Relationships ---")
    
    cite_data = []
    for _, row in df_cites.iterrows():
        cite_data.append({
            "source_idx": int(row['Source_Index']),
            "target_idx": int(row['Target_Index'])
        })
        
    query_citations = """
    UNWIND $rows AS row
    MATCH (source:Document {index: row.source_idx})
    MATCH (target:Document {index: row.target_idx})
    MERGE (source)-[:CITES]->(target)
    """
    
    graph.query(query_citations, params={"rows": cite_data})
    print(f" > Created {len(cite_data)} citation links.")

    # 7. Final Stats
    print("\n--- Final Summary ---")
    stats = graph.query("""
    MATCH (n) 
    RETURN labels(n) as Label, count(*) as Count
    ORDER BY Count DESC
    """)
    for s in stats:
        print(f" {s['Label']}: {s['Count']}")
        
    rel_stats = graph.query("MATCH ()-[r]->() RETURN type(r) as Type, count(*) as Count")
    for s in rel_stats:
        print(f" [REL] {s['Type']}: {s['Count']}")

if __name__ == "__main__":
    build_graph()
