import os
import psycopg2
import ollama
from dotenv import load_dotenv

load_dotenv()

PG_USER = os.getenv("PG_USER")
PG_PASS = os.getenv("PG_PASS")
PG_DATABASE = os.getenv("PG_DATABASE")
PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT")

# 1. Connect to your local PostgreSQL database
conn = psycopg2.connect(
    dbname=PG_DATABASE,
    user=PG_USER,
    password=PG_PASS,
    host=PG_HOST,
    port=PG_PORT
)
cur = conn.cursor()

# 2. Fetch all rubrics that do not have an embedding yet
# We use 'rubric' as the column name based on your CSV extraction
cur.execute("""
    SELECT id, fullpath 
    FROM rubric 
    WHERE abbrev = 'publicum' AND embedding IS NULL;
""")
rows = cur.fetchall()

print(f"Found {len(rows)} English rubrics to process. Starting embeddings...")

# 3. Loop through the data, embed with Ollama, and update the database
count = 0
for row_id, fullpath_text in rows:
    # Skip if the fullpath is empty or null to avoid embedding errors
    if not fullpath_text:
        continue
        
    # Generate the 768-dimensional vector using nomic-embed-text
    response = ollama.embeddings(model='nomic-embed-text', prompt=fullpath_text)
    vector_array = response['embedding']

    # Update the exact row using the primary key 'id'
    cur.execute(
        "UPDATE rubric SET embedding = %s WHERE id = %s;",
        (vector_array, row_id)
    )
    
    count += 1
    # Save progress to the database every 500 rows
    if count % 500 == 0:
        print(f"Processed {count} rubrics...")
        conn.commit()

# 4. Final commit and close connections
conn.commit()
cur.close()
conn.close()

print("Process complete! All English rubrics have been successfully vectorized.")