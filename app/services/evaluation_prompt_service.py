"""
Evaluation Prompt Service

Fetches the active Gemini evaluation prompt from the `evaluation_prompts`
Supabase table. If the table is empty, auto-seeds it with the built-in
default template so the system always has a prompt to work with.

Placeholders used in the template:
  {transcript}      – formatted interview transcript
  {violations_log}  – proctoring violation log text
  {coding_data}     – coding submissions text
  {rounds_info}     – per-round performance summary text
"""

import uuid
from typing import Optional
from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)

# ── Default prompt (used only for the one-time DB seed) ───────────────────────
DEFAULT_PROMPT_TEMPLATE = """You are an expert technical interview evaluator and behavioral analyst. \
Analyze the following interview data and produce a detailed, honest, and structured candidate evaluation report.

---
## INPUT DATA:
1. Full interview transcript:
{transcript}

2. Proctoring violation log:
{violations_log}

3. Coding submissions:
{coding_data}

{rounds_info}
---

## YOUR EVALUATION TASKS:

### SECTION 1: INTEGRITY ANALYSIS
Analyze for signs of dishonesty, external help, or coaching. Flag unusually long pauses, textbook-perfect answers inconsistent with tone, and overlap with proctoring alerts.

### SECTION 2: TECHNICAL KNOWLEDGE EVALUATION
Evaluate correctness, depth of understanding, knowledge of edge cases, and consistency for each topic.

### SECTION 3: COMMUNICATION & LANGUAGE PROFICIENCY
Analyze communication quality through these four dimensions:
1. Lexical Resource: Diversity, precision, and appropriateness of vocabulary used.
2. Grammatical Range & Accuracy: Variety and complexity of sentence structures and correctness.
3. Fluency & Coherence: Logical flow of ideas, pace of speech, and use of cohesive markers.
4. Pronunciation & Articulated Clarity: Clarity of expression and professional tone (based on transcript cues).

### SECTION 4: PROBLEM SOLVING & LOGICAL REASONING
Analyze clarified questions, thinking out loud, logical progression, and self-correction behavior.

### SECTION 5: BEHAVIORAL & PROFESSIONAL ATTRIBUTES
Evaluate handling of pressure, professional attitude, and ownership of knowledge gaps.

### SECTION 6: PROCTORING & INTEGRITY SUMMARY
Classify violations (MINOR/MODERATE/SEVERE) and identify if they coincide with particularly challenging questions.

### SECTION 7: CODING & ALGORITHMIC ASSESSMENT
Evaluate correctness, quality, complexity (Big O), and problem-solving approach. Perform deep integrity analysis on code (suspiciously perfect code vs. human-like minor errors).

---

## OUTPUT FORMAT:
Your final response MUST be a single, valid JSON object. All string values MUST have quotes properly escaped.
The "overall_feedback" field contains markdown text - ensure all quotes, newlines, and special characters are properly escaped for JSON.

CRITICAL JSON REQUIREMENTS:
- All quotes inside string values MUST be escaped with backslashes (\")
- Newlines in strings MUST be escaped as \n
- Do not include any text outside the JSON object
- The JSON must be valid and parseable by standard JSON parsers
- If the "overall_feedback" contains markdown with quotes, escape them: \"

{
    "overall_score": <number 1-10>,
    "integrity_score": <number 1-10>,
    "technical_knowledge": <number 1-10>,
    "communication_quality": <number 1-10>,
    "problem_solving": <number 1-10>,
    "behavioral_score": <number 1-10>,
    "coding_score": <number 1-10>,
    "integrity_verdict": "CLEAN" | "SUSPICIOUS" | "HIGH RISK",
    "strengths": ["list", "of", "strengths"],
    "areas_for_improvement": ["list", "of", "areas"],
    "overall_feedback": "FULL MARKDOWN REPORT... (ALL QUOTES ESCAPED)",
    "rounds_analysis": [
        {
            "round_name": "...",
            "performance_summary": "...",
            "topics_covered": [],
            "average_rating": <number>
        }
    ]
}

The "overall_feedback" markdown MUST include:
1. ### CANDIDATE SUMMARY
2. ### DETAILED COMMUNICATION ASSESSMENT (Include Lexical, Grammatical, and Fluency breakdown)
3. ### SCORECARD (as a markdown table)
4. ### REASONING & EVIDENCE
5. ### STRENGTHS & RED FLAGS
6. ### AREAS FOR IMPROVEMENT
7. ### CODING EVALUATION (if applicable)

CRITICAL RULE: Do NOT use the terms "Hire" or "Do Not Hire" anywhere in your evaluation. Provide objective analysis without making a final hiring declaration.

Be objective, evidence-based, and reference specific quotes or behaviors from the transcript."""


class EvaluationPromptService:
    """
    Fetches (and optionally updates) the evaluation prompt stored in the
    `evaluation_prompts` Supabase table.
    """

    PROMPT_NAME = "default"

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

    # ── public API ─────────────────────────────────────────────────────────────

    def get_active_prompt(self) -> Optional[str]:
        """
        Return the active prompt template string from the DB.

        If the table is empty, seeds it with DEFAULT_PROMPT_TEMPLATE and
        returns that default.  Returns None only on a hard DB error.
        """
        try:
            response = (
                self.client
                .table("evaluation_prompts")
                .select("prompt_template")
                .eq("name", self.PROMPT_NAME)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )

            if response.data:
                template = response.data[0].get("prompt_template", "").strip()
                if template:
                    logger.info(
                        f"[EvaluationPromptService] ✅ Fetched evaluation prompt "
                        f"(length={len(template)})"
                    )
                    return template

            # Table exists but row is missing — seed it
            logger.warning(
                "[EvaluationPromptService] No active prompt found in DB — "
                "seeding with built-in default."
            )
            self._seed_default()
            return DEFAULT_PROMPT_TEMPLATE

        except Exception as e:
            logger.error(
                f"[EvaluationPromptService] ❌ Error fetching prompt: {e}",
                exc_info=True,
            )
            return None

    def update_prompt(self, template: str) -> bool:
        """
        Upsert the prompt template in the DB.
        Returns True on success, False on failure.
        """
        try:
            now = get_now_ist().isoformat()
            existing = (
                self.client
                .table("evaluation_prompts")
                .select("id")
                .eq("name", self.PROMPT_NAME)
                .execute()
            )

            if existing.data:
                self.client.table("evaluation_prompts").update({
                    "prompt_template": template,
                    "is_active": True,
                    "updated_at": now,
                }).eq("name", self.PROMPT_NAME).execute()
            else:
                self.client.table("evaluation_prompts").insert({
                    "id": str(uuid.uuid4()),
                    "name": self.PROMPT_NAME,
                    "is_active": True,
                    "prompt_template": template,
                    "created_at": now,
                    "updated_at": now,
                }).execute()

            logger.info(
                f"[EvaluationPromptService] ✅ Prompt updated (length={len(template)})"
            )
            return True

        except Exception as e:
            logger.error(
                f"[EvaluationPromptService] ❌ Error updating prompt: {e}",
                exc_info=True,
            )
            return False

    # ── private ────────────────────────────────────────────────────────────────

    def _seed_default(self) -> None:
        """Insert the built-in default prompt so the table is never empty."""
        try:
            now = get_now_ist().isoformat()
            self.client.table("evaluation_prompts").insert({
                "id": str(uuid.uuid4()),
                "name": self.PROMPT_NAME,
                "is_active": True,
                "prompt_template": DEFAULT_PROMPT_TEMPLATE,
                "created_at": now,
                "updated_at": now,
            }).execute()
            logger.info("[EvaluationPromptService] ✅ Seeded default evaluation prompt into DB.")
        except Exception as e:
            logger.warning(f"[EvaluationPromptService] Could not seed default prompt: {e}")
