import os
import psycopg2
import ollama
import re
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

def get_postgres_connection():
    return psycopg2.connect(dbname=PG_DB, user=PG_USER, password=PG_PASS, host=PG_HOST, port=PG_PORT)

def get_neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

# --- Phase 1: Top-K Vector Search ---
def get_top_rubrics(symptom_text, limit=5):
    response = ollama.embeddings(model='nomic-embed-text', prompt=symptom_text)
    query_vector = response['embedding']
    
    pg_conn = get_postgres_connection()
    cur = pg_conn.cursor()
    
    cur.execute("""
        SELECT id, fullpath, (embedding <=> %s::vector) AS distance
        FROM rubric
        WHERE abbrev = 'publicum' AND embedding IS NOT NULL
        ORDER BY distance ASC 
        LIMIT %s;
    """, (query_vector, limit))
    
    candidates = cur.fetchall()
    cur.close()
    pg_conn.close()
    return candidates

# --- Phase 1.5: The LLM Clinical Judge ---
def llm_choose_best_rubric(patient_symptom, candidates):
    # Format the 5 candidates into a clean list for the LLM to read
    options_text = ""
    for r_id, fullpath, distance in candidates:
        options_text += f"- ID: {r_id} | Rubric: {fullpath}\n"

    # We use a strict prompt to force the LLM to act as a medical parser
    prompt = f"""You are an expert homeopathic doctor. 
    A patient reports the following symptom: "{patient_symptom}"
    
    Based on strict anatomical and clinical accuracy, which of the following repertory rubrics is the BEST match?
    
    Options:
    {options_text}
    
    Return ONLY the exact integer ID of the best match. 
    If absolutely none of the options match the correct anatomy (e.g., the symptom is in the stomach but options are for the mouth), return the number 0."""
    
    # Using llama3 (or mistral) for the logical reasoning
    response = ollama.generate(model='llama3:latest', prompt=prompt)
    raw_output = response['response'].strip()
    
    # Extract just the numbers in case the LLM hallucinates extra text
    match = re.search(r'\d+', raw_output)
    if match:
        return int(match.group())
    
    # Fallback to the top vector result if the LLM fails to return an ID
    return candidates[0][0]

# --- Phase 2: Multi-Symptom Graph Repertorisation ---
def repertorize_case(rubric_ids):
    print("\n--- Generating Remedy Matrix ---")
    neo4j_driver = get_neo4j_driver()
    
    cypher_query = """
        MATCH (rem:Remedy)-[rel:HAS_SYMPTOM]->(rub:Rubric)
        WHERE rub.rubric_id IN $rid_list
        RETURN 
            rem.name AS remedy, 
            rem.abbreviation AS abbrev, 
            count(rub) AS symptoms_covered, 
            sum(rel.grade) AS total_score,
            collect(rub.name + ' (Grade ' + toString(rel.grade) + ')') AS matched_rubrics
        ORDER BY symptoms_covered DESC, total_score DESC
        LIMIT 10
    """
    
    with neo4j_driver.session() as session:
        records = session.run(cypher_query, rid_list=rubric_ids)
        matrix = []
        for r in records:
            matrix.append({
                "remedy": r["remedy"],
                "abbrev": r["abbrev"],
                "covered": r["symptoms_covered"],
                "score": r["total_score"],
                "rubrics": r["matched_rubrics"]
            })
            
    neo4j_driver.close()
    return matrix

# --- Execution ---
if __name__ == "__main__":
    patient_case = [
        "My stomach burns really badly right after I drink cold water.",
        "I have severe anxiety when I wake up in the morning.",
        "My joints ache, and it gets much worse when it rains."
    ]
    
    final_rubric_ids = []
    
    print("STEP 1: VECTOR TRANSLATION & LLM RE-RANKING")
    for symptom in patient_case:
        print(f"\nAnalyzing: '{symptom}'")
        candidates = get_top_rubrics(symptom, limit=15)
        
        for i, (r_id, fullpath, distance) in enumerate(candidates):
            print(f"  [{i+1}] {fullpath} (Score: {distance:.3f})")
            
        best_match_id = llm_choose_best_rubric(symptom, candidates)
        
        # Handle the LLM escape hatch
        if best_match_id == 0:
            print("  -> Llama 3 found no suitable anatomical match. Skipping this symptom.")
            continue
        
        # Safely find the text, returning None if the LLM hallucinated a bad ID
        selected_text = next((text for rid, text, dist in candidates if rid == best_match_id), None)
        
        # Fallback mechanism if the LLM glitch returns an invalid ID
        if selected_text is None:
            best_match_id = candidates[0][0]
            selected_text = candidates[0][1]
            print(f"  -> LLM returned an invalid ID. Falling back to top vector: {selected_text} (ID: {best_match_id})")
        else:
            print(f"  -> Llama 3 Selected: {selected_text} (ID: {best_match_id})")
            
        final_rubric_ids.append(best_match_id)
        
    print("\nSTEP 2: NEO4J GRAPH REPERTORISATION")
    if final_rubric_ids:
        remedy_matrix = repertorize_case(final_rubric_ids)
        
        for r in remedy_matrix:
            print(f"{r['remedy']} ({r['abbrev']})")
            print(f"  - Symptoms Covered: {r['covered']} / {len(final_rubric_ids)}")
            print(f"  - Total Grade Score: {r['score']}")
            print(f"  - Matched: {', '.join(r['rubrics'])}\n")
    else:
        print("No valid rubrics were found to repertorize.")