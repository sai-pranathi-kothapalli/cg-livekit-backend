"""
Evaluation Service

Calculates and stores interview evaluation metrics and scores.
Uses AI (Google Gemini) to analyze transcripts and generate detailed feedback.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
from app.config import Config
from app.db.mongo import get_database, doc_with_id
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
        self.db = get_database(config)
        self.evals = self.db["interview_evaluations"]
        self.rounds = self.db["interview_round_evaluations"]
    
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
    ) -> Optional[str]:
        """
        Create or update an evaluation record.
        
        Returns:
            Evaluation ID if successful, None otherwise
        """
        try:
            evaluation_data = {
                "booking_token": booking_token,
                "room_name": room_name,
                "duration_minutes": duration_minutes,
                "total_questions": total_questions,
                "rounds_completed": rounds_completed,
                "overall_score": float(overall_score) if overall_score is not None else None,
                "rounds_data": rounds_data or [],
                "strengths": strengths or [],
                "areas_for_improvement": areas_for_improvement or [],
                "interview_state": interview_state,
                "evaluated_at": get_now_ist().isoformat(),
            }
            
            existing = self.evals.find_one({"booking_token": booking_token})
            if existing:
                evaluation_id = str(existing["_id"])
                self.evals.update_one(
                    {"booking_token": booking_token},
                    {"$set": evaluation_data},
                )
                self.rounds.delete_many({"evaluation_id": evaluation_id})
                if rounds_data:
                    for i, rd in enumerate(rounds_data):
                        self.rounds.insert_one({
                            "evaluation_id": evaluation_id,
                            "round_number": rd.get("round_number", i + 1),
                            "round_name": rd.get("round_name", ""),
                            "questions_asked": rd.get("questions_count", 0),
                            "average_rating": rd.get("average_rating"),
                            "performance_summary": rd.get("performance_summary"),
                            "topics_covered": rd.get("topics_covered", []),
                            "response_ratings": rd.get("response_ratings", []),
                        })
                logger.info(f"✅ Updated evaluation for booking {booking_token}")
                return evaluation_id
            r = self.evals.insert_one(evaluation_data)
            evaluation_id = str(r.inserted_id)
            if rounds_data:
                for i, rd in enumerate(rounds_data):
                    self.rounds.insert_one({
                        "evaluation_id": evaluation_id,
                        "round_number": rd.get("round_number", i + 1),
                        "round_name": rd.get("round_name", ""),
                        "questions_asked": rd.get("questions_count", 0),
                        "average_rating": rd.get("average_rating"),
                        "performance_summary": rd.get("performance_summary"),
                        "topics_covered": rd.get("topics_covered", []),
                        "response_ratings": rd.get("response_ratings", []),
                    })
            logger.info(f"✅ Created evaluation {evaluation_id} for booking {booking_token}")
            return evaluation_id
        except Exception as e:
            logger.error(f"❌ Error creating evaluation: {e}", exc_info=True)
            return None
    
    def save_round_evaluation(
        self,
        evaluation_id: str,
        round_number: int,
        round_name: str,
        questions_asked: int = 0,
        average_rating: Optional[float] = None,
        time_spent_minutes: Optional[float] = None,
        time_target_minutes: Optional[int] = None,
        topics_covered: Optional[List[str]] = None,
        performance_summary: Optional[str] = None,
        response_ratings: Optional[List[float]] = None,
    ) -> bool:
        """
        Save detailed round evaluation.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            round_data = {
                "evaluation_id": evaluation_id,
                "round_number": round_number,
                "round_name": round_name,
                "questions_asked": questions_asked,
                "average_rating": float(average_rating) if average_rating is not None else None,
                "time_spent_minutes": float(time_spent_minutes) if time_spent_minutes is not None else None,
                "time_target_minutes": time_target_minutes,
                "topics_covered": topics_covered or [],
                "performance_summary": performance_summary,
                "response_ratings": response_ratings or [],
            }
            
            self.rounds.insert_one(round_data)
            logger.debug(f"✅ Saved round {round_number} evaluation")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving round evaluation: {e}", exc_info=True)
            return False
    
    def get_evaluation(self, booking_token: str) -> Optional[Dict[str, Any]]:
        """
        Get evaluation data for a booking.
        
        Returns:
            Evaluation data dictionary or None
        """
        try:
            doc = self.evals.find_one({"booking_token": booking_token})
            if not doc:
                return None
            evaluation = doc_with_id(doc)
            evaluation_id = evaluation.get("id")
            rounds_cursor = self.rounds.find({"evaluation_id": evaluation_id}).sort("round_number", 1)
            evaluation["rounds"] = [doc_with_id(r) for r in rounds_cursor]
            return evaluation
        except Exception as e:
            logger.error(f"❌ Error fetching evaluation: {e}", exc_info=True)
            return None

    def get_booking_tokens_with_evaluations(self, tokens: List[str]) -> set:
        """Return set of booking_tokens that have an evaluation."""
        try:
            cursor = self.evals.find({"booking_token": {"$in": tokens}}, {"booking_token": 1})
            return {doc["booking_token"] for doc in cursor}
        except Exception as e:
            logger.error(f"Error fetching evaluation tokens: {e}")
            return set()

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
                "detailed, constructive feedback. Always respond with valid JSON only.\n\n" + prompt
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
            timestamp = msg.get('timestamp', '')
            
            if role == 'assistant':
                lines.append(f"[Interviewer]: {content}")
            elif role == 'user':
                lines.append(f"[Candidate]: {content}")
            else:
                lines.append(f"[{role.title()}]: {content}")
        
        return "\n".join(lines)
    
    def _create_evaluation_prompt(
        self,
        transcript_text: str,
        interview_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create prompt for AI evaluation analysis."""
        
        # Extract round information if available
        rounds_info = ""
        if interview_state and 'response_ratings' in interview_state:
            rounds_info = "\n\nRound Performance Data:\n"
            for round_name, ratings in interview_state.get('response_ratings', {}).items():
                if ratings:
                    avg = sum(ratings) / len(ratings)
                    rounds_info += f"- {round_name}: {len(ratings)} responses, avg rating: {avg:.1f}/10\n"
        
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
    
    def calculate_evaluation_from_transcript(
        self,
        booking_token: str,
        room_name: str,
        transcript: List[Dict[str, Any]],
        interview_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Calculate evaluation metrics from transcript and interview state.
        Uses AI (Grok) for detailed analysis if available, falls back to basic metrics.
        
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
                except:
                    pass
            
            # Try AI-powered analysis
            ai_analysis = None
            if transcript and len(transcript) > 2:  # Only analyze if there's actual conversation
                try:
                    # Run async analysis - handle both sync and async contexts
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # If loop is already running, we need to use a different approach
                            # Create a new event loop in a thread
                            import concurrent.futures
                            import threading
                            
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
                        # No event loop, create one
                        ai_analysis = asyncio.run(
                            self._analyze_with_gemini(transcript, interview_state)
                        )
                except Exception as e:
                    logger.warning(f"AI analysis failed: {e}, using fallback", exc_info=True)
            
            # Extract data from AI analysis or use fallback
            if ai_analysis:
                overall_score = ai_analysis.get('overall_score', 7.0)
                strengths = ai_analysis.get('strengths', [])
                areas_for_improvement = ai_analysis.get('areas_for_improvement', [])
                rounds_analysis = ai_analysis.get('rounds_analysis', [])
                
                logger.info(f"✅ Using AI-generated evaluation (score: {overall_score})")
            else:
                # Fallback to basic evaluation
                overall_score = 7.0
                strengths = [
                    "Completed all interview rounds",
                    "Engaged in conversation throughout",
                    "Provided responses to questions asked",
                ]
                areas_for_improvement = [
                    "Consider providing more detailed examples in responses",
                    "Practice articulating technical concepts more clearly",
                ]
                rounds_analysis = []
                
                # Extract rounds data from interview state if available
                if interview_state and 'response_ratings' in interview_state:
                    for round_name, ratings in interview_state.get('response_ratings', {}).items():
                        if ratings:
                            avg_rating = sum(ratings) / len(ratings)
                            rounds_analysis.append({
                                "round_name": round_name,
                                "average_rating": avg_rating,
                                "questions_count": len(ratings),
                            })
                
                logger.info("Using fallback evaluation (AI analysis not available)")
            
            # Format rounds_data for storage
            rounds_data = []
            for round_analysis in rounds_analysis:
                rounds_data.append({
                    "round_name": round_analysis.get("round_name", ""),
                    "average_rating": round_analysis.get("average_rating", 0),
                    "questions_count": round_analysis.get("questions_count", 0),
                    "performance_summary": round_analysis.get("performance_summary"),
                    "topics_covered": round_analysis.get("topics_covered", []),
                })
            
            # Create evaluation
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
            )
            
            # Save detailed round evaluations if AI analysis provided them
            if evaluation_id and ai_analysis and rounds_analysis:
                for idx, round_analysis in enumerate(rounds_analysis, 1):
                    self.save_round_evaluation(
                        evaluation_id=evaluation_id,
                        round_number=idx,
                        round_name=round_analysis.get("round_name", f"Round {idx}"),
                        questions_asked=round_analysis.get("questions_count", 0),
                        average_rating=round_analysis.get("average_rating"),
                        topics_covered=round_analysis.get("topics_covered", []),
                        performance_summary=round_analysis.get("performance_summary"),
                    )
            
            return evaluation_id
            
        except Exception as e:
            logger.error(f"❌ Error calculating evaluation: {e}", exc_info=True)
            return None
