from config import get_neo4j_driver

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