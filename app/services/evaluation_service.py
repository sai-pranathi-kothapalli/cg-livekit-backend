"""
Evaluation Service

Calculates and stores interview evaluation metrics and scores.
Uses AI (Google Gemini) to analyze transcripts and generate detailed feedback.
"""

import json
import re
import asyncio
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)

# Try to import httpx for Gemini API calls
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not available - AI evaluation will use fallback mode")


class EvaluationService:
    """
    Service for managing interview evaluations.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()
    
    def create_evaluation(
        self,
        booking_token: str,
        room_name: str,
        duration_minutes: Optional[int] = None,
        total_questions: int = 0,
        rounds_completed: int = 0,
        overall_score: Optional[float] = None,
        rounds_data: Optional[List[Dict[str, Any]]] = None,
        strengths: Optional[List[str]] = None,
        areas_for_improvement: Optional[List[str]] = None,
        interview_state: Optional[Dict[str, Any]] = None,
        communication_quality: Optional[float] = None,
        technical_knowledge: Optional[float] = None,
        problem_solving: Optional[float] = None,
        coding_score: Optional[float] = None,
        overall_feedback: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None,
    ) -> Optional[str]:
        """
        Create or update an evaluation record.
        
        Returns:
            Evaluation ID if successful, None otherwise
        """
        try:
            # Prepare interview_state with additional scores/feedback stored in JSON
            if interview_state is None:
                interview_state = {}
            
            # Store additional fields in interview_state["scores"] to preserve data
            if communication_quality is not None or technical_knowledge is not None or \
               problem_solving is not None or coding_score is not None or \
               overall_feedback is not None or token_usage is not None:
                if "scores" not in interview_state:
                    interview_state["scores"] = {}
                
                if communication_quality is not None:
                    interview_state["scores"]["communication_quality"] = float(communication_quality)
                if technical_knowledge is not None:
                    interview_state["scores"]["technical_knowledge"] = float(technical_knowledge)
                if problem_solving is not None:
                    interview_state["scores"]["problem_solving"] = float(problem_solving)
                if coding_score is not None:
                    interview_state["scores"]["coding_score"] = float(coding_score)
                if overall_feedback is not None:
                    interview_state["scores"]["overall_feedback"] = overall_feedback
                if token_usage is not None:
                    interview_state["scores"]["token_usage"] = token_usage
            
            # Only include columns that exist in the evaluations table
            evaluation_data = {
                "booking_token": booking_token,
                "room_name": room_name,
                "duration_minutes": duration_minutes,
                "total_questions": total_questions,
                "rounds_completed": rounds_completed,
                "overall_score": float(overall_score) if overall_score is not None else None,
                "communication_quality": float(communication_quality) if communication_quality is not None else None,
                "technical_knowledge": float(technical_knowledge) if technical_knowledge is not None else None,
                "problem_solving": float(problem_solving) if problem_solving is not None else None,
                "coding_score": float(coding_score) if coding_score is not None else None,
                "overall_feedback": overall_feedback,
                "rounds_data": rounds_data or [],
                "strengths": strengths or [],
                "areas_for_improvement": areas_for_improvement or [],
                "interview_state": interview_state,
                "updated_at": get_now_ist().isoformat(),
            }
            
            # Check if evaluation exists
            response = self.client.table("evaluations").select("id").eq("booking_token", booking_token).execute()
            
            if response.data:
                # Update existing
                evaluation_id = response.data[0]["id"]
                self.client.table("evaluations").update(evaluation_data).eq("booking_token", booking_token).execute()
                logger.info(f"✅ Updated evaluation {evaluation_id} for booking {booking_token}. Score: {evaluation_data.get('overall_score')}")
                return evaluation_id
            else:
                # Create new
                evaluation_data["id"] = str(uuid.uuid4())
                evaluation_data["created_at"] = get_now_ist().isoformat()
                response = self.client.table("evaluations").insert(evaluation_data).execute()
                if not response.data:
                    logger.error(f"❌ Failed to insert evaluation: {response}")
                evaluation_id = response.data[0]["id"] if response.data else evaluation_data["id"]
                logger.info(f"✅ Created evaluation {evaluation_id} for booking {booking_token}. Score: {evaluation_data.get('overall_score')}")
                return evaluation_id
        except Exception as e:
            logger.error(f"❌ Error creating evaluation: {e}", exc_info=True)
            return None
    
    async def update_interview_state(self, booking_token: str, interview_state_update: Dict[str, Any]) -> bool:
        """
        Update the interview_state column in the evaluations table in real-time.
        Useful for persisting session data (violations, code submissions) during the interview.
        """
        try:
            # 1. Get existing evaluation to preserve other fields
            response = self.client.table("evaluations").select("interview_state").eq("booking_token", booking_token).execute()
            
            existing_state = {}
            if response.data:
                existing_state = response.data[0].get("interview_state") or {}
            
            # 2. Merge updates
            # Deep merge simple dicts (scores, violations, code_submissions)
            for key, value in interview_state_update.items():
                if key == "scores" and isinstance(value, dict) and "scores" in existing_state:
                    existing_state["scores"].update(value)
                else:
                    existing_state[key] = value

            # 3. Update DB
            self.client.table("evaluations").update({
                "interview_state": existing_state,
                "updated_at": get_now_ist().isoformat()
            }).eq("booking_token", booking_token).execute()
            
            logger.debug(f"✅ Real-time interview_state update for {booking_token}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update interview_state for {booking_token}: {e}")
            return False

    async def update_token_usage(self, booking_token: str, token_usage: Dict[str, int]) -> bool:
        """
        Update token usage for a booking by storing it in interview_state["scores"]["token_usage"].
        """
        try:
            # Get existing evaluation to preserve interview_state
            response = self.client.table("evaluations").select("interview_state").eq("booking_token", booking_token).execute()
            
            if not response.data:
                logger.warning(f"No evaluation found for booking {booking_token}")
                return False
            
            # Update interview_state with token_usage
            interview_state = response.data[0].get("interview_state") or {}
            if "scores" not in interview_state:
                interview_state["scores"] = {}
            interview_state["scores"]["token_usage"] = token_usage
            
            # Update only interview_state and updated_at
            update_response = self.client.table("evaluations").update({
                "interview_state": interview_state,
                "updated_at": get_now_ist().isoformat(),
            }).eq("booking_token", booking_token).execute()
            
            if update_response.data:
                logger.info(f"✅ Updated token usage for booking {booking_token}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error updating token usage: {e}", exc_info=True)
            return False

    def _create_incremental_evaluation_prompt(self, question: str, answer: str) -> str:
        """Create a prompt for evaluating a single question-answer pair."""
        return f"""
You are an expert technical interviewer evaluator.
Evaluate the candidate's answer to the following technical question.

Question: {question}
Candidate's Answer: {answer}

Provide your evaluation in JSON format with the following fields:
- score: (0-10) A numerical score for the answer's technical correctness and completeness.
- technical_depth: (Low, Medium, High) The level of technical understanding demonstrated.
- feedback: (Short string) A single concise sentence highlighting what was good or what was missing.
- communication: (0-10) A score for how clearly the candidate explained their thought process.

Return ONLY the JSON.
"""

    async def evaluate_answer(
        self,
        booking_token: str,
        question: str,
        answer: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Incrementally evaluate a single question-answer pair.
        Uses a very small prompt to save tokens (< 800 tokens).
        """
        if not HTTPX_AVAILABLE or not self.config.gemini_llm.api_key:
            return None

        prompt = f"""Evaluate this interview Q&A. Be objective.
Question: {question}
Answer: {answer}

Provide JSON:
{{
  "score": <1-10>,
  "technical_depth": <1-10>,
  "communication": <1-10>,
  "feedback": "<concise feedback, max 2 sentences>"
}}"""
        
        # Log input estimate
        input_tokens = len(prompt) // 3
        logger.info(f"📊 [EVAL] Token Estimate: input={input_tokens}")

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.gemini_llm.model}:generateContent"
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "x-goog-api-key": self.config.gemini_llm.api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.2,
                            "response_mime_type": "application/json",
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
            
            if "candidates" in data and data["candidates"]:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                # Log output tokens
                output_tokens = len(text) // 3
                logger.info(f"📊 [EVAL] Token Usage: in={input_tokens}, out={output_tokens}, total={input_tokens+output_tokens}")
                
                result = json.loads(text)
                # Ensure fields exist
                result.setdefault("score", 7)
                result.setdefault("technical_depth", 7)
                result.setdefault("communication", 7)
                result.setdefault("feedback", "Good response.")
                
                # Add context for storage
                result["question"] = question
                result["answer"] = answer
                result["timestamp"] = datetime.utcnow().isoformat() + "Z"
                
                # Store it
                await self.store_answer_evaluation(booking_token, result)
                return result
        except Exception as e:
            logger.warning(f"❌ Incremental evaluation failed: {e}")
            return None

    async def analyze_code(
        self,
        question: str,
        code: str,
        language: str = "python"
    ) -> str:
        """
        Evaluate code submission for correctness, complexity, and quality.
        Securely handles the request on the backend to prevent API key leakage.
        """
        if not HTTPX_AVAILABLE or not self.config.gemini_llm.api_key:
            raise ValueError("AI Analysis service is not configured (missing key or library)")

        prompt = f"""
You are a coding interview evaluator. Analyze this code submission.

Problem: {question or "Analyze the provided code based on general programming principles."}

Language: {language}

Candidate's Code:
{code}

Provide concise feedback (3-4 sentences max):
1. Correctness: Does it solve the problem?
2. Quality: Any bugs or issues?
3. Complexity: Time/space complexity
4. Verdict: Pass/Needs Improvement/Fail

Be encouraging but honest.
        """.strip()

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.gemini_llm.model}:generateContent"
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "x-goog-api-key": self.config.gemini_llm.api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.2,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
            
            if "candidates" in data and data["candidates"]:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                if not text:
                    raise ValueError("Gemini returned an empty response")
                return text.strip()
            
            raise ValueError("No candidates found in Gemini response from Google")

        except Exception as e:
            logger.error(f"❌ Gemini Code Analysis request failed: {e}")
            raise ValueError(f"AI Code Analysis failed: {str(e)}")

    async def store_answer_evaluation(self, booking_token: str, evaluation_data: Dict[str, Any]):
        """
        Append the evaluation to the rounds_data array in Supabase.
        """
        try:
            # Safe append: Fetch current, then Update
            res = self.client.table("evaluations").select("rounds_data").eq("booking_token", booking_token).execute()
            
            if res.data:
                rounds_data = res.data[0].get("rounds_data") or []
                rounds_data.append(evaluation_data)
                
                self.client.table("evaluations").update({
                    "rounds_data": rounds_data,
                    "updated_at": datetime.utcnow().isoformat() + "Z"
                }).eq("booking_token", booking_token).execute()
                logger.info(f"✅ Stored incremental evaluation for booking {booking_token}")
            else:
                # Create original record if it doesn't exist (safety)
                import uuid
                eval_id = str(uuid.uuid4())
                self.client.table("evaluations").insert({
                    "id": eval_id,
                    "booking_token": booking_token,
                    "room_name": "unknown",
                    "rounds_data": [evaluation_data],
                    "rounds_completed": 1,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "updated_at": datetime.utcnow().isoformat() + "Z"
                }).execute()
                logger.info(f"✅ Created evaluation and stored first incremental result for booking {booking_token}")
        except Exception as e:
            logger.error(f"❌ Failed to store incremental evaluation: {e}")

    async def get_evaluation_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get evaluation data for a specific booking token.
        """
        try:
            response = self.client.table("evaluations").select("*").eq("booking_token", token).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching evaluation: {e}")
            return None

    def get_evaluations_for_bookings(self, booking_tokens: List[str]) -> List[Dict[str, Any]]:
        """
        Get evaluations for a list of booking tokens.
        """
        try:
            if not booking_tokens:
                return []
            
            response = self.client.table("evaluations").select("*").in_("booking_token", booking_tokens).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching evaluations for bookings: {e}")
            return []

    def get_evaluation(self, booking_token: str) -> Optional[Dict[str, Any]]:
        """
        Get evaluation data for a booking.
        
        Returns:
            Evaluation data dictionary or None
        """
        try:
            response = self.client.table("evaluations").select("*").eq("booking_token", booking_token).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"❌ Error fetching evaluation: {e}", exc_info=True)
            return None

    def get_booking_tokens_with_evaluations(self, tokens: List[str]) -> set:
        """Return set of booking_tokens that have an evaluation."""
        try:
            response = self.client.table("evaluations").select("booking_token").in_("booking_token", tokens).execute()
            return {row["booking_token"] for row in (response.data or [])}
        except Exception as e:
            logger.error(f"Error fetching evaluation tokens: {e}")
            return set()

    def delete_evaluations_by_booking_tokens(self, tokens: List[str]) -> int:
        """Delete evaluation documents for the given booking tokens. Returns count deleted."""
        if not tokens:
            return 0
        try:
            response = self.client.table("evaluations").delete().in_("booking_token", tokens).execute()
            count = len(response.data) if response.data else 0
            if count > 0:
                logger.info(f"[EvaluationService] Deleted {count} evaluation(s) for {len(tokens)} token(s)")
            return count
        except Exception as e:
            logger.error(f"Error deleting evaluations by tokens: {e}")
            return 0

    async def _analyze_with_gemini(
        self,
        transcript: List[Dict[str, Any]],
        interview_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Use Google Gemini to analyze interview transcript and generate evaluation.
        
        Returns:
            Dictionary with evaluation data or None if analysis fails
        """
        logger.info("🔍 [GEMINI-DEBUG] Starting Gemini API analysis...")
        logger.info(f"🔍 [GEMINI-DEBUG] Transcript length: {len(transcript) if transcript else 0}")
        
        if not HTTPX_AVAILABLE:
            logger.warning("❌ [GEMINI-DEBUG] httpx not available, skipping AI analysis")
            return None
        
        if not self.config.gemini_llm.api_key:
            logger.warning("❌ [GEMINI-DEBUG] Gemini API key not set, using fallback evaluation")
            return None
        
        logger.info("✅ [GEMINI-DEBUG] HTTPX available and API key set, proceeding with analysis...")
        try:
            transcript_text = self._format_transcript_for_analysis(transcript)
            prompt = self._create_evaluation_prompt(transcript_text, interview_state)
            full_prompt = (
                "You are an expert interview evaluator. Analyze interview transcripts and provide "
                "detailed, constructive feedback. Always respond with valid JSON only.\\n\\n" + prompt
            )
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.gemini_llm.model}:generateContent"
            )
            logger.info(f"🌐 [GEMINI-DEBUG] Calling Gemini API: {url}")
            logger.info(f"🌐 [GEMINI-DEBUG] Prompt length: {len(full_prompt)} characters")
            async with httpx.AsyncClient(timeout=90.0) as client:
                logger.info("🌐 [GEMINI-DEBUG] Sending POST request to Gemini API...")
                response = await client.post(
                    url,
                    headers={
                        "x-goog-api-key": self.config.gemini_llm.api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{"parts": [{"text": full_prompt}]}],
                        "generationConfig": {"temperature": 0.3},
                    },
                )
                logger.info(f"🌐 [GEMINI-DEBUG] Response status: {response.status_code}")
                response.raise_for_status()
                data = response.json()
                logger.info("🌐 [GEMINI-DEBUG] Response received, parsing JSON...")
            
            # Log token usage (Gemini returns usageMetadata)
            usage = data.get("usageMetadata") or {}
            input_tokens = usage.get("promptTokenCount") or usage.get("prompt_token_count")
            output_tokens = usage.get("candidatesTokenCount") or usage.get("candidates_token_count")
            total_tokens = usage.get("totalTokenCount") or usage.get("total_token_count")
            if input_tokens is not None or output_tokens is not None or total_tokens is not None:
                logger.info(
                    "📊 [EVAL TOKENS] input=%s output=%s total=%s (context=input)",
                    input_tokens or "—",
                    output_tokens or "—",
                    total_tokens or "—",
                )
            
            content = None
            if "candidates" in data and len(data["candidates"]) > 0:
                cand = data["candidates"][0]
                if "content" in cand and "parts" in cand["content"] and cand["content"]["parts"]:
                    content = cand["content"]["parts"][0].get("text", "")
                    logger.info(f"📝 [GEMINI-DEBUG] Extracted content length: {len(content)} characters")
            if not content:
                logger.warning("❌ [GEMINI-DEBUG] No content in Gemini API response")
                return None
            try:
                logger.info("📝 [GEMINI-DEBUG] Parsing JSON from response...")
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                # Try to parse JSON
                try:
                    analysis = json.loads(content)
                    logger.info("✅ [GEMINI-DEBUG] Successfully parsed JSON, analysis completed")
                    return analysis
                except json.JSONDecodeError as json_err:
                    # Log the error position and surrounding content
                    error_pos = getattr(json_err, 'pos', None)
                    if error_pos:
                        start = max(0, error_pos - 200)
                        end = min(len(content), error_pos + 200)
                        logger.warning(f"❌ [GEMINI-DEBUG] JSON error at position {error_pos}: {json_err}")
                        logger.warning(f"❌ [GEMINI-DEBUG] Content around error: {content[start:end]}")
                    else:
                        logger.warning(f"❌ [GEMINI-DEBUG] JSON error: {json_err}")
                    
                    # Try to fix common JSON issues
                    logger.info("🔧 [GEMINI-DEBUG] Attempting to fix JSON...")
                    fixed_content = self._fix_json_string(content)
                    
                    try:
                        analysis = json.loads(fixed_content)
                        logger.info("✅ [GEMINI-DEBUG] Successfully parsed JSON after fixing, analysis completed")
                        return analysis
                    except json.JSONDecodeError as e2:
                        logger.warning(f"❌ [GEMINI-DEBUG] Still failed after fix attempt: {e2}")
                        
                        # Try one more approach: extract JSON using regex as last resort
                        logger.info("🔧 [GEMINI-DEBUG] Trying regex-based JSON extraction as last resort...")
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            try:
                                extracted_json = json_match.group(0)
                                analysis = json.loads(extracted_json)
                                logger.info("✅ [GEMINI-DEBUG] Successfully parsed JSON using regex extraction")
                                return analysis
                            except json.JSONDecodeError:
                                pass
                        
                        # Final fallback: extract scores from malformed JSON using regex patterns
                        # This preserves the AI-generated scores even when JSON is completely broken
                        logger.info("🔧 [GEMINI-DEBUG] All JSON parsing attempts failed. Attempting score extraction from raw content...")
                        extracted_scores = self._extract_scores_from_malformed_json(content)
                        if extracted_scores:
                            logger.info("✅ [GEMINI-DEBUG] Successfully extracted scores from malformed JSON, using partial analysis")
                            return extracted_scores
                        
                        logger.debug(f"Response content (first 1000 chars): {content[:1000]}")
                        logger.debug(f"Response content (last 1000 chars): {content[-1000:]}")
                        logger.warning("❌ [GEMINI-DEBUG] All parsing and extraction attempts failed, returning None")
                        return None
            except Exception as e:
                logger.warning(f"❌ [GEMINI-DEBUG] Unexpected error parsing JSON: {e}", exc_info=True)
                return None
        except Exception as e:
            logger.warning(f"❌ [GEMINI-DEBUG] AI evaluation analysis failed: {e}, using fallback", exc_info=True)
            return None
    
    def _fix_json_string(self, json_str: str) -> str:
        """
        Attempt to fix common JSON formatting issues in Gemini responses.
        Handles unescaped quotes, newlines, and other common issues.
        """
        import re
        
        # Remove any leading/trailing whitespace
        json_str = json_str.strip()
        
        # Try to find the JSON object boundaries
        # Look for the first { and last }
        first_brace = json_str.find('{')
        last_brace = json_str.rfind('}')
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_str = json_str[first_brace:last_brace + 1]
        
        # Try to fix unescaped quotes in string values
        # We'll use a state machine approach to properly escape quotes inside string values
        result = []
        in_string = False
        escape_next = False
        i = 0
        
        while i < len(json_str):
            char = json_str[i]
            
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                result.append(char)
                escape_next = True
                i += 1
                continue
            
            if char == '"':
                # Check if this is the start/end of a string value
                # Look backwards to see if we're in a key or value context
                if not in_string:
                    # Starting a string
                    in_string = True
                    result.append(char)
                else:
                    # Check if this quote is followed by : or , or } or ]
                    # If so, it's likely the end of a string value
                    peek_ahead = i + 1
                    while peek_ahead < len(json_str) and json_str[peek_ahead] in ' \t\n\r':
                        peek_ahead += 1
                    
                    if peek_ahead < len(json_str):
                        next_char = json_str[peek_ahead]
                        if next_char in [':', ',', '}', ']']:
                            # This is the end of a string
                            in_string = False
                            result.append(char)
                        else:
                            # This is a quote inside a string value - escape it
                            result.append('\\"')
                    else:
                        # End of string, this is the closing quote
                        in_string = False
                        result.append(char)
                i += 1
                continue
            
            # Handle newlines in string values
            if in_string and char == '\n':
                result.append('\\n')
                i += 1
                continue
            
            if in_string and char == '\r':
                # Skip \r (part of \r\n)
                i += 1
                continue
            
            result.append(char)
            i += 1
        
        return ''.join(result)
    
    def _extract_scores_from_malformed_json(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extract scores and key fields from malformed JSON using regex patterns.
        This is a last resort when JSON parsing completely fails.
        
        Returns:
            Dictionary with extracted fields, or None if extraction fails
        """
        try:
            logger.info("🔧 [GEMINI-DEBUG] Attempting to extract scores from malformed JSON using regex...")
            extracted = {}
            
            # Extract numeric scores using regex patterns
            # Pattern: "field_name": <number> or "field_name": <number>,
            score_patterns = {
                'overall_score': r'"overall_score"\s*:\s*(\d+(?:\.\d+)?)',
                'communication_quality': r'"communication_quality"\s*:\s*(\d+(?:\.\d+)?)',
                'technical_knowledge': r'"technical_knowledge"\s*:\s*(\d+(?:\.\d+)?)',
                'problem_solving': r'"problem_solving"\s*:\s*(\d+(?:\.\d+)?)',
                'integrity_score': r'"integrity_score"\s*:\s*(\d+(?:\.\d+)?)',
                'behavioral_score': r'"behavioral_score"\s*:\s*(\d+(?:\.\d+)?)',
                'coding_score': r'"coding_score"\s*:\s*(\d+(?:\.\d+)?)',
            }
            
            for field, pattern in score_patterns.items():
                match = re.search(pattern, content)
                if match:
                    try:
                        value = float(match.group(1))
                        # Validate score is in reasonable range (1-10)
                        if 1.0 <= value <= 10.0:
                            extracted[field] = value
                            logger.debug(f"✅ Extracted {field}: {value}")
                    except (ValueError, IndexError):
                        pass
            
            # Extract string fields (verdicts, recommendations)
            string_patterns = {
                'integrity_verdict': r'"integrity_verdict"\s*:\s*"([^"]+)"',
            }
            
            for field, pattern in string_patterns.items():
                match = re.search(pattern, content)
                if match:
                    try:
                        extracted[field] = match.group(1)
                        logger.debug(f"✅ Extracted {field}: {extracted[field]}")
                    except (IndexError, AttributeError):
                        pass
            
            # Extract arrays (strengths, areas_for_improvement)
            # Pattern: "field_name": ["item1", "item2", ...]
            array_patterns = {
                'strengths': r'"strengths"\s*:\s*\[(.*?)\]',
                'areas_for_improvement': r'"areas_for_improvement"\s*:\s*\[(.*?)\]',
            }
            
            for field, pattern in array_patterns.items():
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    try:
                        array_content = match.group(1)
                        # Extract quoted strings from the array
                        items = re.findall(r'"([^"]+)"', array_content)
                        if items:
                            extracted[field] = items
                            logger.debug(f"✅ Extracted {field}: {len(items)} items")
                    except (IndexError, AttributeError):
                        pass
            
            # Extract overall_feedback (try to get as much as possible)
            # Look for the field and extract until we hit the next field or end
            feedback_match = re.search(r'"overall_feedback"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
            if not feedback_match:
                # Try to extract even if unterminated - get everything until next field
                feedback_match = re.search(r'"overall_feedback"\s*:\s*"((?:(?!").)*?)(?="\s*[,}])', content, re.DOTALL)
            if feedback_match:
                try:
                    feedback = feedback_match.group(1)
                    # Unescape common escape sequences
                    feedback = feedback.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                    # Limit length to prevent extremely long feedback
                    if len(feedback) > 10000:
                        feedback = feedback[:10000] + "\n\n[Feedback truncated due to length]"
                    extracted['overall_feedback'] = feedback
                    logger.debug(f"✅ Extracted overall_feedback: {len(feedback)} chars")
                except (IndexError, AttributeError):
                    pass
            
            # Only return if we extracted at least the overall_score (most critical field)
            if 'overall_score' in extracted:
                logger.info(f"✅ [GEMINI-DEBUG] Successfully extracted scores from malformed JSON. Overall score: {extracted.get('overall_score')}")
                # Fill in missing scores with None (will use fallback defaults in calling code)
                return extracted
            else:
                logger.warning("❌ [GEMINI-DEBUG] Could not extract overall_score from malformed JSON")
                return None
                
        except Exception as e:
            logger.warning(f"❌ [GEMINI-DEBUG] Error extracting scores from malformed JSON: {e}", exc_info=True)
            return None
    
    def _format_transcript_for_analysis(self, transcript: List[Dict[str, Any]]) -> str:
        """Format transcript into readable text for AI analysis."""
        lines = []
        for msg in transcript:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            timestamp = msg.get('timestamp', '')
            
            # Simple timestamp formatting if it's a long string
            ts_str = ""
            if timestamp:
                try:
                    # If it's ISO format, take the time part
                    if 'T' in str(timestamp):
                        ts_str = f"[{str(timestamp).split('T')[1][:8]}] "
                except:
                    pass

            if role == 'assistant':
                lines.append(f"{ts_str}[Interviewer]: {content}")
            elif role == 'user':
                lines.append(f"{ts_str}[Candidate]: {content}")
            else:
                lines.append(f"{ts_str}[{role.title()}]: {content}")
        
        return "\n".join(lines)
    
    def _create_evaluation_prompt(
        self,
        transcript_text: str,
        interview_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build the Gemini evaluation prompt.

        The prompt template is fetched from the `evaluation_prompts` Supabase
        table (active row with name='default').  Dynamic interview data is
        injected via simple string substitution using the four placeholders:
          {transcript}, {violations_log}, {coding_data}, {rounds_info}

        Raises RuntimeError if no prompt is configured in the DB.
        """
        from app.services.evaluation_prompt_service import EvaluationPromptService  # local import to avoid circular deps

        # ── 1. Fetch template from DB ────────────────────────────────────────
        prompt_svc = EvaluationPromptService(self.config)
        template = prompt_svc.get_active_prompt()

        if not template:
            msg = (
                "❌ [EvaluationService] No evaluation prompt found in the database. "
                "Please add a row to the `evaluation_prompts` table (name='default', is_active=true)."
            )
            logger.critical(msg)
            raise RuntimeError(msg)

        # ── 2. Build dynamic sections ────────────────────────────────────────

        # Violations log
        violations_log = "None"
        violations = (interview_state or {}).get("violations", [])
        if violations:
            violations_log = "\n".join([
                f"- [{v.get('timestamp')}] {v.get('alert_type')}: {v.get('message')}"
                for v in violations
            ])

        # Coding submissions
        coding_data = "None"
        code_submissions = (interview_state or {}).get("code_submissions", [])
        if code_submissions:
            coding_data = "\n\n".join([
                f"### Coding Question: {cs.get('question')}\n"
                f"Language: {cs.get('language')}\n"
                f"Timestamp: {cs.get('timestamp')}\n"
                f"--- SUBMITTED CODE ---\n{cs.get('code')}\n--- END CODE ---\n"
                f"Execution Output: {cs.get('execution_output')}\n"
                f"Initial AI Verdict: {cs.get('ai_verdict')}"
                for cs in code_submissions
            ])

        # Round performance summary
        rounds_info = ""
        if interview_state and "response_ratings" in interview_state:
            rounds_info = "\nRound Performance Data:\n"
            for round_name, ratings in interview_state.get("response_ratings", {}).items():
                if ratings:
                    avg = sum(ratings) / len(ratings)
                    rounds_info += f"- {round_name}: {len(ratings)} questions, avg rating: {avg:.1f}/10\n"

        # ── 3. Substitute placeholders ───────────────────────────────────────
        try:
            prompt = template.format(
                transcript=transcript_text,
                violations_log=violations_log,
                coding_data=coding_data,
                rounds_info=rounds_info,
            )
        except KeyError as e:
            logger.error(
                f"[EvaluationService] Prompt template has unknown placeholder: {e}. "
                "Expected: {{transcript}}, {{violations_log}}, {{coding_data}}, {{rounds_info}}"
            )
            raise

        logger.info(f"[EvaluationService] ✅ Prompt assembled from DB template (length={len(prompt)})")
        return prompt
    
    async def _generate_overall_analysis_with_gemini(
        self,
        evaluations: List[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Use Gemini to analyze the student's progress over multiple interviews.
        """
        if not HTTPX_AVAILABLE or not self.config.gemini_llm.api_key:
            return None
            
        try:
            # Prepare data for AI
            summary_data = []
            for ev in evaluations:
                # Extract overall_feedback from interview_state["scores"] if available
                interview_state = ev.get("interview_state") or {}
                scores = interview_state.get("scores") or {}
                overall_feedback = scores.get("overall_feedback") or ""
                
                summary_data.append({
                    "date": ev.get("created_at"),
                    "score": ev.get("overall_score"),
                    "strengths": ev.get("strengths", [])[:3],
                    "improvements": ev.get("areas_for_improvement", [])[:3],
                    "feedback": overall_feedback[:200] if overall_feedback else ""
                })

            prompt = f"""
            Analyze the following student's interview progress over time. 
            The student has completed {len(evaluations)} interviews.
            
            Interview History Data:
            {json.dumps(summary_data, indent=2)}
            
            Provide a concise and encouraging 3-4 sentence overall progress analysis that:
            1. Mentions the score trend (e.g., improvement or consistency).
            2. Highlights recurring strengths.
            3. Points out the most critical areas to keep working on.
            4. Encourages the student.
            
            Respond with the analysis text only, no JSON wrapper.
            """
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.gemini_llm.model}:generateContent"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "x-goog-api-key": self.config.gemini_llm.api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.5},
                    },
                )
                response.raise_for_status()
                data = response.json()
            
            if "candidates" in data and len(data["candidates"]) > 0:
                cand = data["candidates"][0]
                if "content" in cand and "parts" in cand["content"] and cand["content"]["parts"]:
                    return cand["content"]["parts"][0].get("text", "").strip()
            return None
        except Exception as e:
            logger.warning(f"Overall analysis failed: {e}")
            return None
    
    def calculate_evaluation_from_transcript(
        self,
        booking_token: str,
        room_name: str,
        transcript: List[Dict[str, Any]],
        interview_state: Optional[Dict[str, Any]] = None,
        token_usage: Optional[Dict[str, int]] = None,
    ) -> Optional[str]:
        """
        Calculate evaluation metrics from transcript and interview state.
        Uses AI (Gemini) for detailed analysis if available, falls back to basic metrics.
        
        Returns:
            Evaluation ID if successful
        """
        try:
            # Debug logging
            logger.info(f"📊 [EVAL] Starting evaluation for {booking_token}")
            logger.info(f"📊 [EVAL] Transcript length: {len(transcript) if transcript else 0}")
            logger.info(f"📊 [EVAL] Interview state present: {interview_state is not None}")
            logger.info(f"📊 [EVAL] HTTPX available: {HTTPX_AVAILABLE}")
            logger.info(f"📊 [EVAL] Gemini API key set: {bool(self.config.gemini_llm.api_key)}")
            
            ai_analysis = None
            transcript_too_short = False
            
            # Calculate basic metrics first
            user_messages = [m for m in transcript if m.get('role') == 'user']
            assistant_messages = [m for m in transcript if m.get('role') == 'assistant']
            
            total_questions = len(assistant_messages) - 1  # Exclude greeting
            rounds_completed = 5  # Assume all rounds if interview completed
            min_for_ai = self.config.MIN_MESSAGES_FOR_AI_EVALUATION
            
            # Calculate duration (if timestamps available)
            duration_minutes = None
            if transcript and len(transcript) >= 2:
                try:
                    first_time = datetime.fromisoformat(transcript[0].get('timestamp', '').replace('Z', '+00:00'))
                    last_time = datetime.fromisoformat(transcript[-1].get('timestamp', '').replace('Z', '+00:00'))
                    duration_minutes = int((last_time - first_time).total_seconds() / 60)
                except Exception as e:
                    logger.debug(f"[EvaluationService] Could not compute duration from transcript timestamps: {e}")
            
            # 1. Check for existing incremental evaluations in rounds_data
            response = self.client.table("evaluations").select("rounds_data, interview_state").eq("booking_token", booking_token).execute()
            incremental_evals = []
            if response.data:
                incremental_evals = response.data[0].get("rounds_data") or []
                if not interview_state:
                    interview_state = response.data[0].get("interview_state") or {}

            # 2. IMMEDIATE SAVE: Save basic evaluation with token usage to prevent data loss on timeout
            logger.info(f"💾 Saving PRELIMINARY evaluation with token_usage={token_usage}")
            evaluation_id = self.create_evaluation(
                booking_token=booking_token,
                room_name=room_name,
                duration_minutes=duration_minutes,
                total_questions=total_questions,
                rounds_completed=len(incremental_evals) if incremental_evals else rounds_completed,
                overall_score=None, # Pending
                rounds_data=incremental_evals,
                strengths=[],
                areas_for_improvement=[],
                interview_state=interview_state,
                communication_quality=None,
                technical_knowledge=None,
                problem_solving=None,
                coding_score=None,
                overall_feedback="AI analysis in progress...",
                token_usage=token_usage,
            )

            # 3. Aggregate if we have enough incremental evaluations
            if incremental_evals and len(incremental_evals) >= 3:
                logger.info(f"📈 [EVAL] Aggregating {len(incremental_evals)} incremental evaluations for {booking_token}")
                
                sum_score = sum(ev.get("score", 0) for ev in incremental_evals)
                sum_comm = sum(ev.get("communication", 0) for ev in incremental_evals)
                
                avg_score = round(sum_score / len(incremental_evals), 1)
                avg_comm = round(sum_comm / len(incremental_evals), 1)
                
                # Extract strengths and areas for improvement from feedback
                # Simple heuristic: positive feedback for strengths, negative for improvement
                # For now, we'll just collect all feedback and let a smaller summary prompt handle it if needed
                # Or just use the incremental feedback directly as strengths/improvement lists
                
                all_feedback = [ev.get("feedback", "") for ev in incremental_evals]
                
                # We still might want a quick summary prompt to get the final strengths/areas
                # But this prompt will be much smaller since it's just summarizing previous feedback
                
                ai_analysis = {
                    "overall_score": avg_score,
                    "communication_quality": avg_comm,
                    "technical_knowledge": avg_score, # Fallback
                    "problem_solving": avg_score,     # Fallback
                    "coding_score": avg_score,        # Fallback
                    "overall_feedback": "\n".join([f"- {fb}" for fb in all_feedback]),
                    "strengths": [ev.get("feedback") for ev in incremental_evals if ev.get("score", 0) >= 7],
                    "areas_for_improvement": [ev.get("feedback") for ev in incremental_evals if ev.get("score", 0) < 7]
                }
                logger.info(f"✅ [EVAL] Successfully aggregated incremental results. Final Score: {avg_score}")
                # Skip full Gemini analysis if we aggregated successfully
            elif transcript and len(transcript) >= min_for_ai:
                logger.info("🚀 [EVAL] Sufficient transcript but no incremental evals (or < 3). Starting FULL AI analysis...")
                logger.info("🚀 [EVAL-DEBUG] Threshold passed, starting AI analysis...")
                try:
                    # Run async analysis
                    try:
                        logger.info("🔄 [EVAL-DEBUG] Getting event loop...")
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            logger.info("🔄 [EVAL-DEBUG] Loop is running, using ThreadPoolExecutor...")
                            import concurrent.futures
                            
                            def run_async():
                                logger.info("🔄 [EVAL-DEBUG] Creating new event loop in thread...")
                                new_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(new_loop)
                                try:
                                    logger.info("🔄 [EVAL-DEBUG] Calling _analyze_with_gemini in new loop...")
                                    result = new_loop.run_until_complete(
                                        self._analyze_with_gemini(transcript, interview_state)
                                    )
                                    logger.info(f"✅ [EVAL-DEBUG] _analyze_with_gemini returned: {result is not None}")
                                    return result
                                finally:
                                    new_loop.close()
                            
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                logger.info("⏳ [EVAL-DEBUG] Submitting async task to executor...")
                                future = executor.submit(run_async)
                                logger.info("⏳ [EVAL-DEBUG] Waiting for AI analysis result (timeout: 90s)...")
                                ai_analysis = future.result(timeout=90)
                                logger.info(f"✅ [EVAL-DEBUG] AI analysis completed: {ai_analysis is not None}")
                        else:
                            logger.info("🔄 [EVAL-DEBUG] Loop not running, using run_until_complete...")
                            ai_analysis = loop.run_until_complete(
                                self._analyze_with_gemini(transcript, interview_state)
                            )
                            logger.info(f"✅ [EVAL-DEBUG] AI analysis completed: {ai_analysis is not None}")
                    except RuntimeError as re:
                        logger.info(f"🔄 [EVAL-DEBUG] RuntimeError: {re}, using asyncio.run...")
                        ai_analysis = asyncio.run(
                            self._analyze_with_gemini(transcript, interview_state)
                        )
                        logger.info(f"✅ [EVAL-DEBUG] AI analysis completed: {ai_analysis is not None}")
                except Exception as e:
                    logger.warning(f"❌ [EVAL-DEBUG] AI analysis failed: {e}, using fallback", exc_info=True)
            elif transcript and len(transcript) < min_for_ai:
                transcript_too_short = True  # Mark as short transcript scenario
                logger.info(
                    f"⏭️  Skipping Gemini evaluation (interview has {len(transcript)} messages, "
                    f"min for AI evaluation is {min_for_ai}) — using fallback only"
                )
            
            # Extract data from AI analysis or use fallback
            if ai_analysis:
                # Handle scores - use extracted value if present, otherwise fallback to 7.0
                # Note: We check for None explicitly to preserve 0.0 scores if they exist
                overall_score = ai_analysis.get('overall_score')
                if overall_score is None:
                    overall_score = 7.0
                
                communication_quality = ai_analysis.get('communication_quality')
                if communication_quality is None:
                    communication_quality = 7.0
                
                technical_knowledge = ai_analysis.get('technical_knowledge')
                if technical_knowledge is None:
                    technical_knowledge = 7.0
                
                problem_solving = ai_analysis.get('problem_solving')
                if problem_solving is None:
                    problem_solving = 7.0
                
                coding_score = ai_analysis.get('coding_score')
                if coding_score is None:
                    coding_score = 7.0
                
                strengths = ai_analysis.get('strengths') or []
                areas_for_improvement = ai_analysis.get('areas_for_improvement') or []
                # rounds_analysis removed - no longer storing rounds data
                overall_feedback = ai_analysis.get('overall_feedback') or "Interview completed successfully."
                
                # Log if this was a partial extraction (only some fields)
                extracted_fields = [k for k in ['overall_score', 'communication_quality', 'technical_knowledge', 
                                                'problem_solving', 'coding_score', 'strengths', 
                                                'areas_for_improvement', 'overall_feedback'] if k in ai_analysis]
                if len(extracted_fields) < 7:
                    logger.info(f"✅ Using AI-generated evaluation (partial extraction: {extracted_fields}, score: {overall_score})")
                else:
                    logger.info(f"✅ Using AI-generated evaluation (score: {overall_score})")
            else:
                # Determine fallback score and feedback based on reason
                if transcript_too_short:
                    # Short transcript scenario - NO SCORES, just feedback
                    transcript_count = len(transcript) if transcript else 0
                    overall_score = 0.0  # Assign 0.0 instead of None to mark as finished
                    communication_quality = 0.0
                    technical_knowledge = 0.0
                    problem_solving = 0.0
                    coding_score = 0.0

                    overall_feedback = (
                        f"⚠️ **Insufficient Conversation for Detailed Analysis**\n\n"
                        f"The interview had only {transcript_count} message(s), which is below the minimum threshold "
                        f"of {min_for_ai} messages required for AI-powered evaluation. "
                        f"To receive a comprehensive performance analysis, please ensure the interview includes "
                        f"sufficient conversation and interaction.\n\n"
                        f"**What this means:**\n"
                        f"- Basic interview metrics have been captured (duration, questions asked, rounds completed)\n"
                        f"- Detailed AI analysis was not performed due to limited conversation data\n"
                        f"- For a complete evaluation, please complete a full interview session with adequate interaction"
                    )
                    strengths = [
                        "Interview session initiated",
                        "Basic participation recorded",
                    ]
                    areas_for_improvement = [
                        "Complete a full interview session with sufficient conversation to receive detailed feedback",
                        "Engage in all interview rounds to allow comprehensive performance evaluation",
                    ]
                    logger.info(f"Using fallback evaluation - transcript too short ({transcript_count} < {min_for_ai} messages) - NO SCORES ASSIGNED")
                else:
                    # Other failure scenarios (API errors, etc.) - still provide scores
                    overall_score = 5.0
                    communication_quality = 5.0
                    technical_knowledge = 5.0
                    problem_solving = 5.0
                    coding_score = 5.0
                    overall_feedback = (
                        "The interview has been completed and basic metrics have been captured. "
                        "Detailed AI-powered analysis was unavailable for this session due to technical limitations. "
                        "Please contact support if you believe this is an error."
                    )
                    strengths = [
                        "Completed all interview rounds",
                        "Engaged in conversation throughout",
                        "Provided responses to questions asked",
                    ]
                    areas_for_improvement = [
                        "Consider providing more detailed examples in responses",
                        "Practice articulating technical concepts more clearly",
                    ]
                    logger.info("Using fallback evaluation (AI analysis not available - technical issue)")
            
            # Create final evaluation (rounds_data no longer stored)
            evaluation_id = self.create_evaluation(
                booking_token=booking_token,
                room_name=room_name,
                duration_minutes=duration_minutes,
                total_questions=total_questions,
                rounds_completed=rounds_completed,
                overall_score=overall_score,
                rounds_data=incremental_evals,  # Preserve the incremental rounds data
                strengths=strengths,
                areas_for_improvement=areas_for_improvement,
                interview_state=interview_state,
                communication_quality=communication_quality,
                technical_knowledge=technical_knowledge,
                problem_solving=problem_solving,
                coding_score=coding_score,
                overall_feedback=overall_feedback,
                token_usage=token_usage,
            )
            return evaluation_id
            
        except Exception as e:
            logger.error(f"❌ Error calculating evaluation: {e}", exc_info=True)
            return None

    def get_student_analytics(self, booking_tokens: List[str]) -> Dict[str, Any]:
        """
        Calculate analytics for a student based on their interview history.
        """
        try:
            if not booking_tokens:
                return {
                    "total_interviews": 0,
                    "average_scores": {
                        "overall": 0,
                        "communication": 0,
                        "technical": 0,
                        "problem_solving": 0
                    },
                    "history": [],
                    "recent_strengths": [],
                    "recent_improvements": []
                }

            evaluations = self.get_evaluations_for_bookings(booking_tokens)
            
            # Filter out evaluations with None scores (pending AI analysis)
            evaluations = [e for e in evaluations if e.get("overall_score") is not None]
            
            # Sort by created_at (oldest to newest) to show progress
            evaluations.sort(key=lambda x: x.get("created_at", ""))
            
            total = len(evaluations)
            if total == 0:
                return {
                    "total_interviews": 0,
                    "average_scores": {
                        "overall": 0,
                        "communication": 0,
                        "technical": 0,
                        "problem_solving": 0
                    },
                    "history": [],
                    "recent_strengths": [],
                    "recent_improvements": []
                }

            sum_overall = 0.0
            sum_comm = 0.0
            sum_tech = 0.0
            sum_prob = 0.0
            sum_coding = 0.0
            
            history = []
            all_strengths = []
            all_improvements = []

            for eval_data in evaluations:
                # Extract scores from interview_state["scores"] if available
                interview_state = eval_data.get("interview_state") or {}
                scores = interview_state.get("scores") or {}
                
                # Stats - read from interview_state["scores"] or default to 0
                score = float(eval_data.get("overall_score") or 0)
                comm = float(scores.get("communication_quality") or 0)
                tech = float(scores.get("technical_knowledge") or 0)
                prob = float(scores.get("problem_solving") or 0)
                coding = float(scores.get("coding_score") or 0)
                
                sum_overall += score
                sum_comm += comm
                sum_tech += tech
                sum_prob += prob
                sum_coding += coding
                
                # History point
                history.append({
                    "date": eval_data.get("created_at"),
                    "score": score,
                    "communication": comm,
                    "technical": tech,
                    "problem_solving": prob,
                    "coding": coding
                })
                
                # Collect strengths/improvements (prioritize more recent ones)
                if eval_data.get("strengths"):
                    all_strengths.extend(eval_data.get("strengths"))
                if eval_data.get("areas_for_improvement"):
                    all_improvements.extend(eval_data.get("areas_for_improvement"))

            # unique and limit (5 most recent unique items)
            # Reverse to get most recent first, then unique, then take first 5
            unique_strengths = []
            seen_s = set()
            for s in reversed(all_strengths):
                if s not in seen_s:
                    unique_strengths.append(s)
                    seen_s.add(s)
            unique_strengths = unique_strengths[:5]

            unique_improvements = []
            seen_i = set()
            for i in reversed(all_improvements):
                if i not in seen_i:
                    unique_improvements.append(i)
                    seen_i.add(i)
            unique_improvements = unique_improvements[:5]
            
            result = {
                "total_interviews": total,
                "average_scores": {
                    "overall": round(sum_overall / total, 1),
                    "communication": round(sum_comm / total, 1),
                    "technical": round(sum_tech / total, 1),
                    "problem_solving": round(sum_prob / total, 1),
                    "coding": round(sum_coding / total, 1)
                },
                "history": history,
                "recent_strengths": unique_strengths,
                "recent_improvements": unique_improvements,
                "overall_analysis": None
            }
            
            # Generate AI analysis if there are 2+ interviews
            if total >= 2:
                try:
                    # Run async analysis
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        def run_sync():
                            new_loop = asyncio.new_event_loop()
                            try:
                                return new_loop.run_until_complete(self._generate_overall_analysis_with_gemini(evaluations))
                            finally:
                                new_loop.close()
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            result["overall_analysis"] = executor.submit(run_sync).result(timeout=45)
                    else:
                        result["overall_analysis"] = loop.run_until_complete(self._generate_overall_analysis_with_gemini(evaluations))
                except Exception as e:
                    logger.warning(f"Failed to generate overall analysis: {e}")
            
            return result
        except Exception as e:
            logger.error(f"Error calculating student analytics: {e}", exc_info=True)
            return {
                "total_interviews": 0,
                "average_scores": {},
                "history": [],
                "error": str(e)
            }
