import os
import psycopg2
import ollama
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

PG_USER = os.getenv("PG_USER")
PG_PASS = os.getenv("PG_PASS")
PG_DB = os.getenv("PG_DATABASE")
PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT")

NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASS = os.getenv("NEO4J_PASS")
NEO4J_URI = "neo4j://localhost:7687" 

# --- Database Connections ---
def get_postgres_connection():
    return psycopg2.connect(
        dbname=PG_DB, 
        user=PG_USER, 
        password=PG_PASS, 
        host=PG_HOST, 
        port=PG_PORT
    )

def get_neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

# --- Core Logic ---
def solve_symptom(patient_sentence):
    print(f"\nAnalyzing Symptom: '{patient_sentence}'\n" + "-"*50)
    
    # 1. Embed the patient's sentence using your local Ollama model
    print("1. Generating semantic embedding...")
    response = ollama.embeddings(model='nomic-embed-text', prompt=patient_sentence)
    query_vector = response['embedding']
    
    # 2. Query PostgreSQL to find the closest matching formal Rubric
    print("2. Searching PostgreSQL for the closest clinical rubric...")
    pg_conn = get_postgres_connection()
    cur = pg_conn.cursor()
    
    # Using <=> for cosine distance in pgvector to find the best semantic match
    cur.execute("""
        SELECT id, fullpath 
        FROM rubric 
        WHERE abbrev = 'publicum' AND embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector 
        LIMIT 1;
    """, (query_vector,))
    
    result = cur.fetchone()
    cur.close()
    pg_conn.close()
    
    if not result:
        print("No matching rubric found.")
        return
        
    rubric_id, fullpath = result
    print(f"-> Translated to Rubric: {fullpath} (ID: {rubric_id})\n")
    
    # 3. Query Neo4j to get the connected remedies and their grades
    print("3. Querying Neo4j for indicated remedies...")
    neo4j_driver = get_neo4j_driver()
    
    cypher_query = """
        MATCH (rem:Remedy)-[rel:HAS_SYMPTOM]->(rub:Rubric {rubric_id: $rid})
        RETURN rem.name AS remedy, rem.abbreviation AS abbrev, rel.grade AS grade
        ORDER BY grade DESC, remedy ASC
        LIMIT 10
    """
    
    with neo4j_driver.session() as session:
        records = session.run(cypher_query, rid=rubric_id)
        remedies = [{"remedy": r["remedy"], "abbrev": r["abbrev"], "grade": r["grade"]} for r in records]
        
    neo4j_driver.close()
    
    # 4. Display the results
    if not remedies:
        print(f"-> No remedies mapped to this specific rubric in the graph.")
    else:
        print("Top Indicated Remedies:")
        for r in remedies:
            print(f"- {r['remedy']} ({r['abbrev']}) : Grade {r['grade']}")

# --- Test the Engine ---
if __name__ == "__main__":
    test_sentence = "My stomach burns really badly right after I drink cold water."
    solve_symptom(test_sentence)