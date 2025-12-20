import os
import sys
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_openai import ChatOpenAI

# 1. Configuration
# Check if API Key is present
if "OPENAI_API_KEY" not in os.environ:
    print("Error: OPENAI_API_KEY environment variable is not set.")
    sys.exit(1)

NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "testpassword"

def main():
    print("--- Initializing Neo4j & LLM Connection ---")
    
    # 2. Connect to Neo4j
    try:
        graph = Neo4jGraph(
            url=NEO4J_URI, 
            username=NEO4J_USER, 
            password=NEO4J_PASSWORD,
            enhanced_schema=False,
            refresh_schema=False
        )
        
        # Manually define schema because we bypassed automatic refresh
        graph.schema = """
        Node properties:
        - **Person**
          - `name`: STRING
          - `role`: STRING
        Relationship properties:
        - **FRIEND**
        - **WORK_WITH**
        The relationships are:
        (:Person)-[:FRIEND]->(:Person)
        (:Person)-[:WORK_WITH]->(:Person)
        """
        print(" > Neo4j Connected & Schema Manually Loaded")
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        return

    # 3. Setup LLM (using gpt-4o or gpt-3.5-turbo)
    # temperature=0 ensures deterministic (consistent) query generation
    llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")

    # 4. Create the Chain
    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        verbose=True,  # Shows the internal steps (Generated Cypher etc.)
        allow_dangerous_requests=True
    )

    # 5. Non-Interactive Execution
    print("\n" + "="*50)
    print("Executing Example Questions...")
    print("="*50 + "\n")

    questions = [
        "Kim의 친구는 누구야?",
        "Manager 역할을 하는 사람은 누구야?",
        "Lee와 Kim은 어떤 관계야?"
    ]

    for q in questions:
        print(f"Question: {q}")
        try:
            response = chain.invoke({"query": q})
            print(f"Answer: {response['result']}\n")
            print("-" * 30)
        except Exception as e:
            print(f"Error processing question: {e}")

if __name__ == "__main__":
    main()
