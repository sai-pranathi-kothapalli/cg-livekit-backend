import json
from app.db.supabase import get_supabase
from app.config import get_config

def update():
    config = get_config()
    client = get_supabase()
    
    # 1. Fetch current prompt
    res = client.table('evaluation_prompts').select('*').eq('name', 'default').execute()
    if not res.data:
        print("❌ Default prompt not found")
        return

    p = res.data[0]['prompt_template']
    
    # 2. Update JSON Schema and Instructions
    if '"confidence_level":' not in p:
        p = p.replace(
            '    "coding_score": <number 1-10>,', 
            '    "coding_score": <number 1-10>,\n    "confidence_level": <number 1-10>,'
        )
        print("✅ Added confidence_level to JSON schema")

    # 3. Add Confidence Rubric
    CONFIDENCE_RUBRIC = """
    Confidence Level (1-10):
    - 1-3: Candidate gives very short answers, frequently says "I don't know", long silences, refuses questions.
    - 4-6: Some hesitation, occasional short answers, recovers when prompted.
    - 7-9: Speaks clearly and directly, elaborates without prompting.
    - 10: Exceptional clarity, strong opinions, handles all questions confidently.
    """
    
    if "Confidence Level (1-10):" not in p:
        # Inject before REASONING
        p = p.replace('3. ### REASONING', f"{CONFIDENCE_RUBRIC}\n\n3. ### REASONING")
        print("✅ Added Confidence Rubric to instructions")

    # 4. Update Formatting Instructions for Reasoning
    if '(Use bullet points for category analysis)' not in p:
        p = p.replace(
            '3. ### REASONING', 
            '3. ### REASONING\n   - CRITICAL: Use a bulleted list format for the reasoning. Categorize points under bold headers for each assessment area (Communication, Technical Knowledge, Problem Solving, Integrity, Behavioral). Each point should be a concise bullet.'
        )
        print("✅ Added bulleted reasoning instructions")

    # 4. Save back to DB
    client.table('evaluation_prompts').update({'prompt_template': p}).eq('name', 'default').execute()
    print("🚀 Prompt template updated successfully in Supabase.")

if __name__ == "__main__":
    update()
