"""
Application Processing Service

Handles application file upload, text extraction, and storage.
"""

import re
from io import BytesIO
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

import json
from openai import AsyncOpenAI

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None

from app.config import Config
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError

logger = get_logger(__name__)


class ResumeService:
    """Service for processing application files"""
    
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx'}
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }
    
    def __init__(self, config: Config):
        self.config = config
        
    def validate_file(self, file_content: bytes, filename: str, content_type: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate application file.
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            content_type: MIME type of file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        if len(file_content) > self.MAX_FILE_SIZE:
            return False, f"File size exceeds maximum of {self.MAX_FILE_SIZE / 1024 / 1024}MB"
        
        # Check extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.ALLOWED_EXTENSIONS:
            return False, f"File type not supported. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}"
        
        # Check MIME type if provided
        if content_type and content_type not in self.ALLOWED_MIME_TYPES:
            return False, f"Invalid file type. Expected PDF or DOC/DOCX"
        
        return True, None
    
    def extract_text(self, file_content: bytes, filename: str, content_type: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        Extract text from application file.
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            content_type: MIME type of file
            
        Returns:
            Tuple of (extracted_text, error_message)
        """
        file_ext = Path(filename).suffix.lower()
        
        try:
            if file_ext == '.pdf':
                return self._extract_pdf_text(file_content)
            elif file_ext in ['.doc', '.docx']:
                return self._extract_docx_text(file_content)
            else:
                return "", f"Unsupported file type: {file_ext}"
        except Exception as e:
            error_msg = f"Failed to extract text: {str(e)}"
            logger.error(f"[ResumeService] {error_msg}", exc_info=True)
            return "", error_msg
    
    def _extract_pdf_text(self, file_content: bytes) -> Tuple[str, Optional[str]]:
        """Extract text from PDF file"""
        if PdfReader is None:
            return "", "PyPDF2 library not installed"
        
        try:
            pdf_file = BytesIO(file_content)
            reader = PdfReader(pdf_file)
            
            text_parts = []
            num_pages = len(reader.pages)
            
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            full_text = '\n'.join(text_parts)
            
            if not full_text or len(full_text.strip()) == 0:
                return "", "PDF appears to be image-based (scanned) - no text content found"
            
            # Clean text
            cleaned_text = self._clean_text(full_text)
            
            logger.info(f"[ResumeService] ✅ PDF extraction complete: {len(cleaned_text)} characters from {num_pages} page(s)")
            
            if len(cleaned_text) < 50:
                logger.warning(f"[ResumeService] ⚠️ Extracted text is very short ({len(cleaned_text)} chars)")
            
            return cleaned_text, None
            
        except Exception as e:
            error_msg = f"PDF extraction error: {str(e)}"
            logger.error(f"[ResumeService] {error_msg}", exc_info=True)
            return "", error_msg
    
    def _extract_docx_text(self, file_content: bytes) -> Tuple[str, Optional[str]]:
        """Extract text from DOC/DOCX file"""
        if Document is None:
            return "", "python-docx library not installed"
        
        try:
            doc_file = BytesIO(file_content)
            doc = Document(doc_file)
            
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            
            full_text = '\n'.join(text_parts)
            
            if not full_text or len(full_text.strip()) == 0:
                return "", "Document appears to be empty"
            
            # Clean text
            cleaned_text = self._clean_text(full_text)
            
            logger.info(f"[ResumeService] ✅ DOCX extraction complete: {len(cleaned_text)} characters")
            
            if len(cleaned_text) < 50:
                logger.warning(f"[ResumeService] ⚠️ Extracted text is very short ({len(cleaned_text)} chars)")
            
            return cleaned_text, None
            
        except Exception as e:
            error_msg = f"DOCX extraction error: {str(e)}"
            logger.error(f"[ResumeService] {error_msg}", exc_info=True)
            return "", error_msg
    
    async def parse_application_data(self, text: str) -> Dict[str, Any]:
        """
        Parse extracted text into structured application data using OpenAI-compatible LLM.
        
        Args:
            text: Extracted text from resume/application
            
        Returns:
            Dictionary of application form fields
        """
        if not self.config.openai.api_key or not self.config.openai.llm_base_url:
            logger.warning("[ResumeService] OpenAI API key or base URL not configured - skipping AI parsing")
            return {}
            
        try:
            client = AsyncOpenAI(
                api_key=self.config.openai.api_key,
                base_url=self.config.openai.llm_base_url,
            )
            
            # Create comprehensive prompt for extracting all application form fields
            prompt = f"""Extract all application form information from the following text and return as JSON.

Extract the following fields (use null if not found):

PERSONAL DETAILS:
- full_name (or name)
- post
- category
- date_of_birth (or dob) - format as YYYY-MM-DD if possible
- gender
- marital_status
- aadhaar_number (or aadhaar)
- pan_number (or pan)
- father_name (or father)
- mother_name (or mother)
- spouse_name (or spouse) - only if married

ADDRESS DETAILS:
- correspondence_address1 (or correspondence_address)
- correspondence_address2
- correspondence_address3
- correspondence_state
- correspondence_district
- correspondence_pincode (or correspondence_pin)
- permanent_address1 (or permanent_address)
- permanent_address2
- permanent_address3
- permanent_state
- permanent_district
- permanent_pincode (or permanent_pin)

CONTACT:
- mobile_number (or phone, mobile)
- alternative_number (or alternate_phone)

EDUCATIONAL QUALIFICATION:
- ssc_board
- ssc_passing_date
- ssc_percentage
- ssc_class
- graduation_degree (or degree)
- graduation_college (or college)
- graduation_specialization (or specialization)
- graduation_passing_date
- graduation_percentage
- graduation_class

OTHER DETAILS:
- religion
- religious_minority (boolean)
- local_language_studied (boolean)
- local_language_name
- computer_knowledge (boolean)
- computer_knowledge_details
- languages_known (object with language names as keys)

APPLICATION SPECIFIC:
- state_applying_for (or state)
- regional_rural_bank (or rrb)
- exam_center_preference1
- exam_center_preference2
- medium_of_paper

Return ONLY valid JSON. Use null for missing fields. For boolean fields, use true/false.

Text to extract from:
{text[:8000]}  # Limit text to avoid token limits
"""
            
            response = await client.chat.completions.create(
                model=self.config.openai.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that extracts structured data from resumes and application forms. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            
            if response.choices and response.choices[0].message.content:
                return json.loads(response.choices[0].message.content)
            return {}
            
        except Exception as e:
            logger.error(f"[ResumeService] AI parsing failed: {str(e)}", exc_info=True)
            return {}

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Normalize line breaks
        text = re.sub(r'\n\s*\n', '\n', text)
        # Trim
        text = text.strip()
        
        return text

