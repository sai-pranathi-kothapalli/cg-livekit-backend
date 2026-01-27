"""
Interview State Management Service

Tracks interview progress, rounds, time, and questions asked.
"""

from datetime import datetime
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from app.utils.datetime_utils import get_now_ist

@dataclass
class InterviewState:
    """Tracks interview progress and state"""
    
    interview_start_time: datetime
    current_round: str = "round1_self_intro"
    round_start_time: datetime = field(default_factory=get_now_ist)
    questions_asked_per_round: Dict[str, Set[str]] = field(default_factory=dict)
    candidate_info: Dict = field(default_factory=dict)
    round_completed: Dict[str, bool] = field(default_factory=dict)
    response_ratings: Dict[str, list] = field(default_factory=dict)  # Round -> list of ratings
    
    # Time targets from PDF (cumulative minutes from start)
    ROUND_TIME_TARGETS = {
        "round1_self_intro": 7,      # End by 7 min
        "round2_gk_current_affairs": 17,  # End by 17 min
        "round3_domain_knowledge": 29,     # End by 29 min
        "round4_banking_rrb": 44,          # End by 44 min
        "round5_situational": 50           # Hard stop at 50 min
    }
    
    ROUND_ORDER = [
        "round1_self_intro",
        "round2_gk_current_affairs",
        "round3_domain_knowledge",
        "round4_banking_rrb",  # MANDATORY - cannot skip
        "round5_situational"
    ]
    
    def should_transition_to_next_round(self) -> bool:
        """Check if it's time to move to next round based on time targets"""
        elapsed = (get_now_ist() - self.interview_start_time).total_seconds() / 60
        
        if self.current_round in self.ROUND_TIME_TARGETS:
            target_time = self.ROUND_TIME_TARGETS[self.current_round]
            return elapsed >= target_time
        
        return False
    
    def get_time_remaining_in_round(self) -> float:
        """Get minutes remaining in current round"""
        elapsed = (get_now_ist() - self.interview_start_time).total_seconds() / 60
        
        if self.current_round in self.ROUND_TIME_TARGETS:
            target_time = self.ROUND_TIME_TARGETS[self.current_round]
            return max(0, target_time - elapsed)
        
        return 0
    
    def get_total_elapsed_time(self) -> float:
        """Get total elapsed time in minutes"""
        return (get_now_ist() - self.interview_start_time).total_seconds() / 60
    
    def mark_question_asked(self, round_name: str, question: str):
        """Track which questions have been asked"""
        if round_name not in self.questions_asked_per_round:
            self.questions_asked_per_round[round_name] = set()
        self.questions_asked_per_round[round_name].add(question)
    
    def get_next_round(self) -> Optional[str]:
        """Get the next round in sequence"""
        try:
            current_index = self.ROUND_ORDER.index(self.current_round)
            if current_index < len(self.ROUND_ORDER) - 1:
                return self.ROUND_ORDER[current_index + 1]
        except ValueError:
            pass
        
        return None
    
    def transition_to_next_round(self) -> Optional[str]:
        """Transition to next round and return round name"""
        next_round = self.get_next_round()
        if next_round:
            self.round_completed[self.current_round] = True
            self.current_round = next_round
            self.round_start_time = get_now_ist()
            return next_round
        return None
    
    def record_response_rating(self, round_name: str, rating: int):
        """Record response rating (0-10 scale)"""
        if round_name not in self.response_ratings:
            self.response_ratings[round_name] = []
        self.response_ratings[round_name].append(rating)
    
    def update_candidate_info(self, key: str, value: any):
        """Update candidate information"""
        self.candidate_info[key] = value

