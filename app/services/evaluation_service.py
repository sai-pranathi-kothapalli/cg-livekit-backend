"""
Evaluation Service

Calculates and stores interview evaluation metrics and scores.
Uses AI (Google Gemini) to analyze transcripts and generate detailed feedback.
"""

import json
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
        overall_feedback: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None,
    ) -> Optional[str]:
        """
        Create or update an evaluation record.
        
        Returns:
            Evaluation ID if successful, None otherwise
        """
        try:
            evaluation_data = {
                "booking_token": booking_token,
                "overall_score": float(overall_score) if overall_score is not None else None,
                "strengths": strengths or [],
                "areas_for_improvement": areas_for_improvement or [],
                "rounds": rounds_data or [],
                "communication_quality": float(communication_quality) if communication_quality is not None else None,
                "technical_knowledge": float(technical_knowledge) if technical_knowledge is not None else None,
                "problem_solving": float(problem_solving) if problem_solving is not None else None,
                "overall_feedback": overall_feedback,
                "interview_metrics": {
                    "duration_minutes": duration_minutes,
                    "total_questions": total_questions,
                    "rounds_completed": rounds_completed,
                    "room_name": room_name,
                    "interview_state": interview_state
                },
                "token_usage": token_usage,
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
    
    async def update_token_usage(self, booking_token: str, token_usage: Dict[str, int]) -> bool:
        """
        Update token usage for a booking.
        """
        try:
            response = self.client.table("evaluations").update({
                "token_usage": token_usage
            }).eq("booking_token", booking_token).execute()
            
            if response.data:
                logger.info(f"✅ Updated token usage for booking {booking_token}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error updating token usage: {e}", exc_info=True)
            return False

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
        if not HTTPX_AVAILABLE:
            logger.warning("httpx not available, skipping AI analysis")
            return None
        
        if not self.config.gemini_llm.api_key:
            logger.debug("Gemini API key not set, using fallback evaluation")
            return None
        
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
            async with httpx.AsyncClient(timeout=60.0) as client:
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
                response.raise_for_status()
                data = response.json()
            
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
            if not content:
                logger.warning("No content in Gemini API response")
                return None
            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                analysis = json.loads(content)
                logger.info("✅ AI evaluation analysis completed (Gemini)")
                return analysis
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Gemini response as JSON: {e}")
                logger.debug(f"Response content: {content[:500]}")
                return None
        except Exception as e:
            logger.warning(f"⚠️  AI evaluation analysis failed: {e}, using fallback")
            return None
    
    def _format_transcript_for_analysis(self, transcript: List[Dict[str, Any]]) -> str:
        """Format transcript into readable text for AI analysis."""
        lines = []
        for i, msg in enumerate(transcript):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            
            if role == 'assistant':
                lines.append(f"[Interviewer]: {content}")
            elif role == 'user':
                lines.append(f"[Candidate]: {content}")
            else:
                lines.append(f"[{role.title()}]: {content}")
        
        return "\\n".join(lines)
    
    def _create_evaluation_prompt(
        self,
        transcript_text: str,
        interview_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create prompt for AI evaluation analysis."""
        
        # Extract round information if available
        rounds_info = ""
        if interview_state and 'response_ratings' in interview_state:
            rounds_info = "\\n\\nRound Performance Data:\\n"
            for round_name, ratings in interview_state.get('response_ratings', {}).items():
                if ratings:
                    avg = sum(ratings) / len(ratings)
                    rounds_info += f"- {round_name}: {len(ratings)} responses, avg rating: {avg:.1f}/10\\n"
        
        prompt = f"""Analyze the following interview transcript and provide a comprehensive evaluation.

Interview Transcript:
{transcript_text}
{rounds_info}

Please provide a detailed evaluation in the following JSON format:
{{
    "overall_score": <number between 0-10>,
    "strengths": [
        "<specific strength 1>",
        "<specific strength 2>",
        "<specific strength 3>"
    ],
    "areas_for_improvement": [
        "<specific area 1>",
        "<specific area 2>",
        "<specific area 3>"
    ],
    "rounds_analysis": [
        {{
            "round_name": "<round name>",
            "performance_summary": "<brief summary of performance in this round>",
            "topics_covered": ["<topic1>", "<topic2>"],
            "average_rating": <number 0-10>,
            "strengths": ["<strength>"],
            "improvements": ["<improvement>"]
        }}
    ],
    "communication_quality": <number 0-10>,
    "technical_knowledge": <number 0-10>,
    "problem_solving": <number 0-10>,
    "overall_feedback": "<comprehensive feedback paragraph>"
}}

Evaluation Criteria:
1. Communication Skills: Clarity, articulation, confidence
2. Technical Knowledge: Depth of understanding, accuracy
3. Problem Solving: Analytical thinking, practical solutions
4. Engagement: Active participation, question understanding
5. Professionalism: Demeanor, attitude, preparation

Be specific and constructive. Base scores on actual performance in the transcript."""
        
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
                summary_data.append({
                    "date": ev.get("created_at"),
                    "score": ev.get("overall_score"),
                    "strengths": ev.get("strengths", [])[:3],
                    "improvements": ev.get("areas_for_improvement", [])[:3],
                    "feedback": ev.get("overall_feedback", "")[:200]
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
            # Calculate basic metrics first
            user_messages = [m for m in transcript if m.get('role') == 'user']
            assistant_messages = [m for m in transcript if m.get('role') == 'assistant']
            
            total_questions = len(assistant_messages) - 1  # Exclude greeting
            rounds_completed = 5  # Assume all rounds if interview completed
            
            # Calculate duration (if timestamps available)
            duration_minutes = None
            if transcript and len(transcript) >= 2:
                try:
                    first_time = datetime.fromisoformat(transcript[0].get('timestamp', '').replace('Z', '+00:00'))
                    last_time = datetime.fromisoformat(transcript[-1].get('timestamp', '').replace('Z', '+00:00'))
                    duration_minutes = int((last_time - first_time).total_seconds() / 60)
                except Exception as e:
                    logger.debug(f"[EvaluationService] Could not compute duration from transcript timestamps: {e}")
            
            # Extract rounds data from interview state if available
            rounds_analysis = []
            if interview_state and 'response_ratings' in interview_state:
                for round_name, ratings in interview_state.get('response_ratings', {}).items():
                    if ratings:
                        avg_rating = sum(ratings) / len(ratings)
                        rounds_analysis.append({
                            "round_name": round_name,
                            "average_rating": avg_rating,
                            "questions_count": len(ratings),
                        })
            
            # 1. IMMEDIATE SAVE: Save basic evaluation with token usage to prevent data loss on timeout
            basic_rounds_data = []
            for ra in rounds_analysis:
                basic_rounds_data.append({
                    "round_name": ra.get("round_name", ""),
                    "average_rating": ra.get("average_rating", 0),
                    "questions_count": ra.get("questions_count", 0),
                    "performance_summary": "Pending AI analysis...",
                    "topics_covered": [],
                })
                
            logger.info(f"💾 Saving PRELIMINARY evaluation with token_usage={token_usage}")
            evaluation_id = self.create_evaluation(
                booking_token=booking_token,
                room_name=room_name,
                duration_minutes=duration_minutes,
                total_questions=total_questions,
                rounds_completed=rounds_completed,
                overall_score=None, # Pending
                rounds_data=basic_rounds_data,
                strengths=[],
                areas_for_improvement=[],
                interview_state=interview_state,
                communication_quality=None,
                technical_knowledge=None,
                problem_solving=None,
                overall_feedback="AI analysis in progress...",
                token_usage=token_usage,
            )

            # Try AI-powered analysis (skip Gemini for short interviews to save cost)
            ai_analysis = None
            min_for_ai = getattr(self.config, "MIN_MESSAGES_FOR_AI_EVALUATION", 8)
            if transcript and len(transcript) >= min_for_ai:
                try:
                    # Run async analysis
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            import concurrent.futures
                            
                            def run_async():
                                new_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(new_loop)
                                try:
                                    return new_loop.run_until_complete(
                                        self._analyze_with_gemini(transcript, interview_state)
                                    )
                                finally:
                                    new_loop.close()
                            
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(run_async)
                                ai_analysis = future.result(timeout=90)
                        else:
                            ai_analysis = loop.run_until_complete(
                                self._analyze_with_gemini(transcript, interview_state)
                            )
                    except RuntimeError:
                        ai_analysis = asyncio.run(
                            self._analyze_with_gemini(transcript, interview_state)
                        )
                except Exception as e:
                    logger.warning(f"AI analysis failed: {e}, using fallback", exc_info=True)
            elif transcript and len(transcript) < min_for_ai:
                logger.info(
                    f"⏭️  Skipping Gemini evaluation (interview has {len(transcript)} messages, "
                    f"min for AI evaluation is {min_for_ai}) — using fallback only"
                )
            
            # Extract data from AI analysis or use fallback
            if ai_analysis:
                overall_score = ai_analysis.get('overall_score') or 7.0
                strengths = ai_analysis.get('strengths') or []
                areas_for_improvement = ai_analysis.get('areas_for_improvement') or []
                rounds_analysis = ai_analysis.get('rounds_analysis') or []
                communication_quality = ai_analysis.get('communication_quality') or 7.0
                technical_knowledge = ai_analysis.get('technical_knowledge') or 7.0
                problem_solving = ai_analysis.get('problem_solving') or 7.0
                overall_feedback = ai_analysis.get('overall_feedback') or "Interview completed successfully."
                logger.info(f"✅ Using AI-generated evaluation (score: {overall_score})")
            else:
                overall_score = 7.0
                communication_quality = 7.0
                technical_knowledge = 7.0
                problem_solving = 7.0
                overall_feedback = (
                    "The interview has been completed and basic metrics have been captured. "
                    "Detailed AI-powered analysis was skipped or unavailable for this session."
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
                logger.info("Using fallback evaluation (AI analysis not available)")
            
            # Format rounds_data for storage (FINAL)
            rounds_data = []
            if ai_analysis:
                for round_analysis in rounds_analysis:
                    rounds_data.append({
                        "round_name": round_analysis.get("round_name", ""),
                        "average_rating": round_analysis.get("average_rating", 0),
                        "questions_count": round_analysis.get("questions_count", 0),
                        "performance_summary": round_analysis.get("performance_summary"),
                        "topics_covered": round_analysis.get("topics_covered", []),
                    })
            else:
                # Use basic metrics calculated earlier if AI skipped
                for ra in basic_rounds_data:
                    rounds_data.append({
                        "round_name": ra.get("round_name", ""),
                        "average_rating": ra.get("average_rating", 0),
                        "questions_count": ra.get("questions_count", 0),
                        "performance_summary": "Handled successfully.",
                        "topics_covered": [],
                    })
            
            # Create final evaluation
            evaluation_id = self.create_evaluation(
                booking_token=booking_token,
                room_name=room_name,
                duration_minutes=duration_minutes,
                total_questions=total_questions,
                rounds_completed=rounds_completed,
                overall_score=overall_score,
                rounds_data=rounds_data,
                strengths=strengths,
                areas_for_improvement=areas_for_improvement,
                interview_state=interview_state,
                communication_quality=communication_quality,
                technical_knowledge=technical_knowledge,
                problem_solving=problem_solving,
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
            
            history = []
            all_strengths = []
            all_improvements = []

            for eval_data in evaluations:
                # Stats
                score = float(eval_data.get("overall_score") or 0)
                comm = float(eval_data.get("communication_quality") or 0)
                tech = float(eval_data.get("technical_knowledge") or 0)
                prob = float(eval_data.get("problem_solving") or 0)
                
                sum_overall += score
                sum_comm += comm
                sum_tech += tech
                sum_prob += prob
                
                # History point
                history.append({
                    "date": eval_data.get("created_at"),
                    "score": score,
                    "communication": comm,
                    "technical": tech,
                    "problem_solving": prob
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
                    "problem_solving": round(sum_prob / total, 1)
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
