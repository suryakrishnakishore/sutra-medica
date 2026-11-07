from vector_search import get_top_rubrics
from llm_agent import llm_choose_best_rubric
from graph_engine import repertorize_case

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
        # Overriding default limit to 15 based on the original script usage
        candidates = get_top_rubrics(symptom, limit=15)
        
        for i, (r_id, fullpath, distance) in enumerate(candidates):
            print(f"  [{i+1}] {fullpath} (Score: {distance:.3f})")
            
        best_match_id = llm_choose_best_rubric(symptom, candidates)
        
        if best_match_id == 0:
            print("  -> Llama 3 found no suitable anatomical match. Skipping this symptom.")
            continue
        
        selected_text = next((text for rid, text, dist in candidates if rid == best_match_id), None)
        
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