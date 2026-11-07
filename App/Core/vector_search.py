import ollama
from config import get_postgres_connection

def get_top_rubrics(symptom_text, limit=15):
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