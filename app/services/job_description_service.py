"""
Job Description Service

Handles job description CRUD operations with Supabase.
"""

from typing import Optional, Dict, Any
from supabase import create_client, Client
from app.config import Config
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class JobDescriptionService:
    """Service for managing job descriptions"""
    
    JD_ID = '00000000-0000-0000-0000-000000000001'  # Single JD row ID
    
    def __init__(self, config: Config):
        self.config = config
        self.supabase: Client = create_client(
            config.supabase.url,
            config.supabase.service_role_key
        )
    
    def get_job_description(self) -> Dict[str, Any]:
        """
        Get current job description.
        
        Returns:
            Job description data dict with default values if not found
        """
        try:
            result = self.supabase.table('job_descriptions')\
                .select('*')\
                .eq('id', self.JD_ID)\
                .maybe_single()\
                .execute()
            
            if result.data:
                logger.info("[JobDescriptionService] Found job description in database")
                return {
                    'title': result.data.get('title', ''),
                    'description': result.data.get('description', ''),
                    'requirements': result.data.get('requirements', ''),
                    'preparation_areas': result.data.get('preparation_areas', []),
                }
            else:
                # Return default values if not found
                logger.info("[JobDescriptionService] No job description found, returning defaults")
                return self._get_default_jd()
                
        except Exception as e:
            logger.error(f"[JobDescriptionService] Error fetching job description: {str(e)}", exc_info=True)
            # Return defaults on error
            return self._get_default_jd()
    
    def update_job_description(
        self,
        title: str,
        description: str,
        requirements: str,
        preparation_areas: list
    ) -> Dict[str, Any]:
        """
        Update job description.
        
        Args:
            title: Job title
            description: Job description
            requirements: Job requirements
            preparation_areas: List of preparation areas
            
        Returns:
            Updated job description data dict
            
        Raises:
            AgentError: If update fails
        """
        try:
            jd_data = {
                'title': title,
                'description': description,
                'requirements': requirements,
                'preparation_areas': preparation_areas,
                'updated_at': get_now_ist().isoformat(),
            }
            
            # Try to update existing record
            result = self.supabase.table('job_descriptions')\
                .update(jd_data)\
                .eq('id', self.JD_ID)\
                .execute()
            
            if result.data:
                logger.info("[JobDescriptionService] ✅ Updated job description")
                return {
                    'title': result.data[0].get('title', ''),
                    'description': result.data[0].get('description', ''),
                    'requirements': result.data[0].get('requirements', ''),
                    'preparation_areas': result.data[0].get('preparation_areas', []),
                }
            else:
                # If update didn't work, try insert
                jd_data['id'] = self.JD_ID
                result = self.supabase.table('job_descriptions')\
                    .insert(jd_data)\
                    .execute()
                
                if result.data:
                    logger.info("[JobDescriptionService] ✅ Created job description")
                    return {
                        'title': result.data[0].get('title', ''),
                        'description': result.data[0].get('description', ''),
                        'requirements': result.data[0].get('requirements', ''),
                        'preparation_areas': result.data[0].get('preparation_areas', []),
                    }
                else:
                    raise AgentError("Failed to save job description: No data returned", "job_description")
                
        except Exception as e:
            error_msg = f"Failed to update job description: {str(e)}"
            logger.error(f"[JobDescriptionService] {error_msg}", exc_info=True)
            raise AgentError(error_msg, "job_description")
    
    def _get_default_jd(self) -> Dict[str, Any]:
        """Get default job description values"""
        return {
            'title': 'Regional Rural Bank Probationary Officer (PO)',
            'description': 'We are conducting interviews for the Regional Rural Bank Probationary Officer (PO) position. This is an excellent opportunity to build a career in the banking sector and serve rural communities through financial inclusion and banking services.',
            'requirements': 'Graduation degree from a recognized university. Knowledge of local language. Computer literacy.',
            'preparation_areas': [
                'Candidate Personal Introduction: Your background, education, and motivation',
                'Background/History of Regional Rural Bank: Understanding of RRBs, their structure and role',
                'Current Affairs for Banking: Recent developments in banking sector, RBI policies, government schemes',
                'Domain Knowledge: Banking fundamentals, operations, and financial awareness'
            ]
        }

