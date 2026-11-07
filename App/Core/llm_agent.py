import ollama
import re

def llm_choose_best_rubric(patient_symptom, candidates):
    options_text = ""
    for r_id, fullpath, distance in candidates:
        options_text += f"- ID: {r_id} | Rubric: {fullpath}\n"

    prompt = f"""You are an expert homeopathic doctor. 
    A patient reports the following symptom: "{patient_symptom}"
    
    Based on strict anatomical and clinical accuracy, which of the following repertory rubrics is the BEST match?
    
    Options:
    {options_text}
    
    Return ONLY the exact integer ID of the best match. 
    If absolutely none of the options match the correct anatomy (e.g., the symptom is in the stomach but options are for the mouth), return the number 0."""
    
    response = ollama.generate(model='llama3:latest', prompt=prompt)
    raw_output = response['response'].strip()
    
    match = re.search(r'\d+', raw_output)
    if match:
        return int(match.group())
    
    return candidates[0][0]