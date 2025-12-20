import os
import sys
from langchain_neo4j import Neo4jGraph

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

def seed_data():
    print("--- Connecting to Neo4j ---")
    try:
        # Connect without APOC checks
        graph = Neo4jGraph(
            url=NEO4J_URI, 
            username=NEO4J_USER, 
            password=NEO4J_PASSWORD,
            enhanced_schema=False,
            refresh_schema=False
        )
        print("Connected.")
    except Exception as e:
        print(f"Connection Failed: {e}")
        return

    # 1. Clean up existing data
    print("--- Cleaning Database ---")
    graph.query("MATCH (n) DETACH DELETE n")
    
    # 2. Create Constraints (Optional but good practice)
    # Note: Using try-catch in Cypher via Python loop if needed, but for simplicity just creating nodes.
    
    print("--- Seeding Data ---")
    
    seed_query = """
    // 1. Teams
    MERGE (t_eng:Team {name: 'Engineering', description: 'Develops the core product'})
    MERGE (t_des:Team {name: 'Design', description: 'UI/UX and branding'})
    MERGE (t_prod:Team {name: 'Product', description: 'Product strategy and roadmap'})

    // 2. People
    MERGE (alice:Person {name: 'Alice', role: 'CTO', bio: 'Expert in AI and scalability.'})
    MERGE (bob:Person {name: 'Bob', role: 'Senior Developer', bio: 'Loves Python and Graph DBs.'})
    MERGE (charlie:Person {name: 'Charlie', role: 'DevOps Engineer', bio: 'Focuses on CI/CD and cloud infra.'})
    MERGE (david:Person {name: 'David', role: 'Product Designer', bio: 'User-centric design approach.'})
    MERGE (eve:Person {name: 'Eve', role: 'Product Manager', bio: 'Bridges gap between tech and business.'})
    MERGE (frank:Person {name: 'Frank', role: 'Intern', bio: 'Learning Neo4j and AI.'})

    // 3. Relationships: WORKS_IN & MANAGES
    MERGE (alice)-[:WORKS_IN]->(t_eng)
    MERGE (bob)-[:WORKS_IN]->(t_eng)
    MERGE (charlie)-[:WORKS_IN]->(t_eng)
    MERGE (david)-[:WORKS_IN]->(t_des)
    MERGE (eve)-[:WORKS_IN]->(t_prod)
    MERGE (frank)-[:WORKS_IN]->(t_eng)

    MERGE (alice)-[:MANAGES]->(bob)
    MERGE (alice)-[:MANAGES]->(charlie)
    MERGE (eve)-[:MANAGES]->(david)
    MERGE (bob)-[:MENTORS]->(frank)

    // 4. Topics (Tech Stack & Concepts)
    MERGE (ai:Topic {name: 'Artificial Intelligence'})
    MERGE (graph:Topic {name: 'Graph Database'})
    MERGE (python:Topic {name: 'Python'})
    MERGE (cloud:Topic {name: 'Cloud Computing'})
    MERGE (ux:Topic {name: 'User Experience'})

    // 5. Documents (Unstructured Data for RAG)
    MERGE (d1:Document {
        title: 'Project Apollo Kickoff', 
        content: 'Project Apollo aims to integrate AI into our core platform. Alice will lead the architecture. We will use Neo4j for data storage.'
    })
    MERGE (d2:Document {
        title: 'Q3 DevOps Strategy', 
        content: 'Charlie proposed moving our infrastructure to a hybrid cloud. Security compliance is a priority for the Engineering team.'
    })
    MERGE (d3:Document {
        title: 'Design System Update', 
        content: 'David is updating the design system to support new mobile layouts. Focus on accessibility and UX consistency.'
    })
    MERGE (d4:Document {
        title: 'Internship Plan', 
        content: 'Frank will be studying Graph RAG methodologies under Bob supervision. The goal is to build a prototype using Python.'
    })

    // 6. Linking Documents to Entities (Context for RAG)
    MERGE (alice)-[:AUTHORED]->(d1)
    MERGE (charlie)-[:AUTHORED]->(d2)
    MERGE (david)-[:AUTHORED]->(d3)
    MERGE (bob)-[:AUTHORED]->(d4)

    // Mentions (Explicit links from text to graph entities)
    MERGE (d1)-[:MENTIONS]->(alice)
    MERGE (d1)-[:MENTIONS]->(ai)
    MERGE (d1)-[:MENTIONS]->(graph)
    
    MERGE (d2)-[:MENTIONS]->(charlie)
    MERGE (d2)-[:MENTIONS]->(cloud)
    MERGE (d2)-[:MENTIONS]->(t_eng)
    
    MERGE (d3)-[:MENTIONS]->(david)
    MERGE (d3)-[:MENTIONS]->(ux)
    
    MERGE (d4)-[:MENTIONS]->(frank)
    MERGE (d4)-[:MENTIONS]->(bob)
    MERGE (d4)-[:MENTIONS]->(graph)
    MERGE (d4)-[:MENTIONS]->(python)

    RETURN count(*) as nodes_created
    """
    
    result = graph.query(seed_query)
    print(f"--- Data Seeded Successfully ---")
    print(f"Nodes Created/Touched (approx): {result}")

    # Verify
    print("\n--- Summary ---")
    summary = graph.query("""
    MATCH (n) 
    RETURN labels(n) as Label, count(*) as Count 
    ORDER BY Count DESC
    """)
    for record in summary:
        print(f"{record['Label']}: {record['Count']}")

if __name__ == "__main__":
    seed_data()
