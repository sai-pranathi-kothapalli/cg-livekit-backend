"""
Question Bank Service

Manages question tracking and dynamic generation.
Note: Static question bank has been removed in favor of the combined prompt in professional_arjun.py.
"""

from typing import Dict, List, Optional, Set
from app.services.interview_state_service import InterviewState

class QuestionBankService:
    """Manages dynamic question generation and tracking"""
    
    def __init__(self, interview_state: InterviewState):
        self.interview_state = interview_state
        # Static question bank removed to use single source of truth in worker prompt
        self.question_banks = {}
    
    def get_next_question(
        self, 
        round_name: str, 
        candidate_context: Dict,
        llm_client=None
    ) -> str:
        """
        Generate next question dynamically using LLM.
        The static bank is removed to prevent redundancy with the worker prompt.
        """
        # Always generate dynamically or return a prompt for the LLM to handle
        return self._generate_new_question(round_name, candidate_context, llm_client)
    
    def _get_available_questions(self, round_name: str) -> List[str]:
        """Deprecated: Static bank removed"""
        return []
    
    async def _generate_new_question(
        self, 
        round_name: str, 
        candidate_context: Dict,
        llm_client
    ) -> str:
        """Generate new question when bank is exhausted"""
        if not llm_client:
            # Fallback
            return "Can you elaborate more on this topic?"
        
        round_info = self.question_banks.get(round_name, {})
        asked = list(self.interview_state.questions_asked_per_round.get(round_name, set()))
        
        from app.services.prompt_service import get_prompt_service
        prompt_service = get_prompt_service()
        base_prompt = await prompt_service.get_prompt(
            "question_generation_fallback",
            default_content="Generate a NEW interview question for {round_name} round."
        )
        
        # Format the fetched prompt with context variables
        try:
            prompt = base_prompt.format(
                round_name=round_name,
                objective=round_info.get('objective', 'Assess candidate knowledge'),
                candidate_context=candidate_context,
                previous_questions=asked[-5:]
            )
        except KeyError:
            # Fallback if keys don't match e.g. if DB prompt was edited incorrectly
            prompt = f"""
            Generate a NEW interview question for {round_name} round.
            
            Round Objectives: {round_info.get('objective', 'Assess candidate knowledge')}
            Candidate Background: {candidate_context}
            
            Generate ONLY the question text.
            """
        
        try:
            response = await llm_client.generate_content(prompt)
            question = response.text.strip()
            self.interview_state.mark_question_asked(round_name, question)
            return question
        except Exception as e:
            return "Can you elaborate more on this topic?"

