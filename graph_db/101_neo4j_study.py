from neo4j import GraphDatabase
import time

# --- 1. CONFIGURATION ---
# Connect to localhost. Protocol is 'neo4j' (standard).
# Port 7687 is for the Bolt protocol (data), 7474 is for the Browser UI.
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "testpassword")

def wait_for_neo4j():
    """Waits for Neo4j to be ready."""
    print("Connecting to Neo4j...")
    retries = 15
    driver = GraphDatabase.driver(URI, auth=AUTH)
    while retries > 0:
        try:
            driver.verify_connectivity()
            print("Connected successfully!")
            return driver
        except Exception:
            print(f"Waiting for Neo4j to start... ({retries} retries left)")
            time.sleep(2)
            retries -= 1
    driver.close()
    raise Exception("Could not connect to Neo4j. Check if the Docker container is running.")

# --- 2. CORE CONCEPTS & HELPER FUNCTIONS ---

def create_initial_data(tx):
    """
    Cypher Query Basics:
    - MERGE: Creates if not exists (prevents duplicates).
    - (n:Label {prop: 'val'}): Node with a Label and Properties.
    - (a)-[:REL_TYPE]->(b): A relationship from 'a' to 'b'.
    """
    print("  > Executing Cypher to create nodes and relationships...")
    query = """
    MERGE (kim:Person {name: 'Kim', role: 'Developer'})
    MERGE (lee:Person {name: 'Lee', role: 'Designer'})
    MERGE (park:Person {name: 'Park', role: 'Manager'})
    
    MERGE (kim)-[:FRIEND]->(lee)
    MERGE (kim)-[:FRIEND]->(park)
    MERGE (lee)-[:WORK_WITH]->(park)
    """
    tx.run(query)

def find_friends_of_kim(tx):
    """
    Querying:
    - MATCH: Pattern matching.
    - RETURN: Specifying what data to extract.
    """
    print("  > Querying: Who is friends with Kim?")
    query = """
    MATCH (p:Person {name: 'Kim'})-[:FRIEND]->(friend)
    RETURN friend.name AS FriendName, friend.role AS FriendRole
    """
    result = tx.run(query)
    return [record.data() for record in result]

def clean_database(tx):
    """Deletes everything (USE WITH CAUTION)."""
    print("  > Cleaning database for a fresh start...")
    tx.run("MATCH (n) DETACH DELETE n")

# --- 3. MAIN EXECUTION ---

if __name__ == "__main__":
    try:
        # Initialize Driver
        driver = wait_for_neo4j()

        with driver.session() as session:
            # 1. Reset
            session.execute_write(clean_database)
            
            # 2. Create
            print("\n--- Creating Data ---")
            session.execute_write(create_initial_data)
            
            # 3. Read
            print("\n--- Querying Data ---")
            friends = session.execute_read(find_friends_of_kim)
            
            print(f"Results found: {len(friends)}")
            for f in friends:
                print(f" - {f['FriendName']} is a {f['FriendRole']}")

        driver.close()
        print("\n[SUCCESS] Neo4j basics completed.")
        print("Note: You can also visit http://localhost:7474 in your browser.")
        print("Login: neo4j / testpassword")

    except Exception as e:
        print(f"\nError: {e}")
