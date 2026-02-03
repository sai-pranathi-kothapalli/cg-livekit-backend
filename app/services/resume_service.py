"""
Application Processing Service

Handles application file upload, text extraction, and storage.
"""

import re
from io import BytesIO
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from datetime import datetime

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

# Labels that start the *next* field in IBPS RRB forms. Used to stop capture so we don't merge fields.
_NEXT_FIELD_LABELS = (
    "Post", "Category", "Date of Birth", "DOB", "D.O.B", "Age completed", "Age as on",
    "Gender", "Marital Status", "Aadhaar", "Aadhaar Card", "Consent to Aadhaar",
    "PAN", "PAN Card", "Do you have twin", "Father's Name", "Mother's Name", "Spouse's Name",
    "Address", "Correspondence", "Permanent Address", "State", "District", "Pincode", "Pin Code",
    "SSC", "Graduation", "Degree", "College", "Board", "Religion", "Mobile", "Phone",
    "Regional Rural Bank", "RRB", "Exam Center", "Medium of Paper",
)

# Section headers in IBPS RRB / CRP application forms. Order matters for chunking.
# Each tuple: (chunk_key, regex_pattern). Pattern is used to find section start (case-insensitive).
_SECTION_HEADERS = (
    ("personal", re.compile(r"Personal\s+Details?", re.IGNORECASE)),
    ("correspondence_address", re.compile(r"Correspondence\s+Address|Address\s+Details?", re.IGNORECASE)),
    ("permanent_address", re.compile(r"Permanent\s+Address", re.IGNORECASE)),
    ("education", re.compile(r"Educational\s+Qualification|Education\s+Details?|SSC\s*[\/]?\s*HSC|Graduation", re.IGNORECASE)),
    ("other", re.compile(r"Other\s+Details?|Declaration|Preference|Exam\s+Center|State\s+Applying", re.IGNORECASE)),
)


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
    
    def _extract_label_value(self, text: str, labels: Tuple[str, ...]) -> Optional[str]:
        """Extract value after any of the given labels. Stops at newline or next form-field label so each field gets only its value."""
        # Build lookahead: stop at newline or any "next field" label (so we don't merge into one field)
        next_labels_alt = "|".join(re.escape(l) for l in _NEXT_FIELD_LABELS)
        stop_lookahead = r"(?=\n|(?:" + next_labels_alt + r")\s*:?)"
        for label in labels:
            # Value = non-greedy match until \n or next label (DOTALL so we can span lines if needed)
            pat = re.compile(
                re.escape(label) + r"\s*:?\s*(.+?)" + stop_lookahead,
                re.IGNORECASE | re.DOTALL,
            )
            m = pat.search(text)
            if m:
                val = m.group(1).strip().strip("-").strip()
                if val and val.lower() not in ("-", "na", "n/a", "nil", "—", "–"):
                    return val
            # Fallback: same line only (for PDFs with newlines between fields)
            pat_line = re.compile(re.escape(label) + r"\s*:?\s*([^\n]+)", re.IGNORECASE)
            m2 = pat_line.search(text)
            if m2:
                val = m2.group(1).strip().strip("-").strip()
                # If value contains a known next-field label, truncate there (same-line merge case)
                for stop in _NEXT_FIELD_LABELS:
                    if stop.lower() in val.lower():
                        idx = val.lower().find(stop.lower())
                        val = val[:idx].strip().strip("-").strip()
                        break
                if val and val.lower() not in ("-", "na", "n/a", "nil", "—", "–"):
                    return val
        return None

    def _normalize_date(self, raw: Optional[str]) -> Optional[str]:
        """Normalize date string to YYYY-MM-DD. Accepts dd-mm-yyyy, dd/mm/yyyy, yyyy-mm-dd."""
        if not raw or not raw.strip():
            return None
        raw = raw.strip()
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y"):
            try:
                dt = datetime.strptime(raw[:10], fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return raw

    def _chunk_by_sections(self, text: str) -> Dict[str, str]:
        """
        Split normalized text into sections by IBPS RRB form headers.
        Returns dict: personal, correspondence_address, permanent_address, education, other.
        Each value is the text from that section header up to the next section (or end).
        Falls back to full text for a key if section not found.
        """
        chunks: Dict[str, str] = {}
        # Find start index of each section
        matches: list[Tuple[str, int]] = []
        for key, pat in _SECTION_HEADERS:
            for m in pat.finditer(text):
                matches.append((key, m.start()))
                break  # first occurrence per section type
        # Sort by position so we can slice between consecutive sections
        matches.sort(key=lambda x: x[1])
        full = text
        for i, (key, start) in enumerate(matches):
            end = matches[i + 1][1] if i + 1 < len(matches) else len(full)
            chunk = full[start:end].strip()
            if chunk:
                chunks[key] = chunk
        # If no sections found, treat whole text as personal (fallback)
        if not chunks:
            chunks["personal"] = full
        # Ensure we have all keys for consistent lookup; missing = use full text
        for key, _ in _SECTION_HEADERS:
            if key not in chunks:
                chunks[key] = full
        return chunks

    async def parse_application_data(self, text: str) -> Dict[str, Any]:
        """
        Parse extracted text into structured application data using regex/heuristics only.
        Chunks text by section first, then extracts each field from the relevant section.
        No external API keys. Suited for IBPS RRB / CRP-style forms.
        """
        if not text or len(text.strip()) < 10:
            return {}
        text_clean = self._clean_text(text)
        chunks = self._chunk_by_sections(text_clean)
        # Resolve which text to use per field (section chunk or full-text fallback)
        personal = chunks.get("personal", text_clean)
        corr_addr = chunks.get("correspondence_address", text_clean)
        perm_addr = chunks.get("permanent_address", text_clean)
        education = chunks.get("education", text_clean)
        other = chunks.get("other", text_clean)
        out: Dict[str, Any] = {}

        # Personal details – from personal section only
        full_name = self._extract_label_value(
            personal,
            ("Full Name", "Name", "Candidate Name", "Applicant Name"),
        )
        if full_name:
            out["full_name"] = full_name

        post = self._extract_label_value(
            personal,
            ("Post", "Post Applied", "Applied For"),
        )
        if post:
            out["post"] = post

        category = self._extract_label_value(
            personal,
            ("Category", "Caste Category", "Category (NCL)"),
        )
        if category:
            out["category"] = category

        dob_raw = self._extract_label_value(
            personal,
            ("Date of Birth", "DOB", "D.O.B", "Birth Date"),
        )
        if dob_raw:
            out["date_of_birth"] = self._normalize_date(dob_raw) or dob_raw

        gender = self._extract_label_value(
            personal,
            ("Gender", "Sex"),
        )
        if gender:
            out["gender"] = gender.strip().upper()

        marital = self._extract_label_value(
            personal,
            ("Marital Status", "Marital", "Marriage Status"),
        )
        if marital:
            out["marital_status"] = marital.strip()

        aadhaar = self._extract_label_value(
            personal,
            ("Aadhaar", "Aadhaar Card Number", "Aadhar", "UID"),
        )
        if aadhaar:
            out["aadhaar_number"] = aadhaar.strip()

        pan = self._extract_label_value(
            personal,
            ("PAN", "PAN Card Number", "Permanent Account Number"),
        )
        if pan:
            out["pan_number"] = pan.strip()

        father = self._extract_label_value(
            personal,
            ("Father's Name", "Father Name", "Fathers Name"),
        )
        if father:
            out["father_name"] = father

        mother = self._extract_label_value(
            personal,
            ("Mother's Name", "Mother Name", "Mothers Name"),
        )
        if mother:
            out["mother_name"] = mother

        spouse = self._extract_label_value(
            personal,
            ("Spouse's Name", "Spouse Name", "Spouse"),
        )
        if spouse:
            out["spouse_name"] = spouse

        # Correspondence address – from correspondence section
        for key, labels in (
            ("correspondence_address1", ("Correspondence Address", "Address Line 1", "Address 1", "Correspondence Add")),
            ("correspondence_state", ("Correspondence State", "State", "Correspondence State")),
            ("correspondence_district", ("Correspondence District", "District", "Corr District")),
            ("correspondence_pincode", ("Correspondence Pincode", "Pincode", "Pin Code", "PIN")),
        ):
            v = self._extract_label_value(corr_addr, labels)
            if v:
                out[key] = v

        # Permanent address – from permanent section
        for key, labels in (
            ("permanent_address1", ("Permanent Address", "Permanent Add", "Address Line 1")),
            ("permanent_state", ("Permanent State", "Permanent State")),
            ("permanent_district", ("Permanent District", "Permanent District")),
            ("permanent_pincode", ("Permanent Pincode", "Permanent Pin")),
        ):
            v = self._extract_label_value(perm_addr, labels)
            if v:
                out[key] = v

        # Contact – personal or full (often near personal)
        mobile = self._extract_label_value(
            personal,
            ("Mobile", "Mobile Number", "Phone", "Contact Number", "Mobile No"),
        )
        if not mobile:
            mobile = self._extract_label_value(
                text_clean,
                ("Mobile", "Mobile Number", "Phone", "Contact Number", "Mobile No"),
            )
        if mobile:
            out["mobile_number"] = mobile.strip()

        # Education – from education section only
        for key, labels in (
            ("ssc_board", ("SSC Board", "10th Board", "Board (SSC)")),
            ("ssc_passing_date", ("SSC Passing", "SSC Year", "10th Passing")),
            ("ssc_percentage", ("SSC Percentage", "SSC %", "10th Percentage")),
            ("ssc_class", ("SSC Class", "10th Class")),
            ("graduation_degree", ("Graduation Degree", "Degree", "Graduate Degree")),
            ("graduation_college", ("Graduation College", "College", "Graduate College")),
            ("graduation_specialization", ("Specialization", "Graduation Specialization")),
            ("graduation_passing_date", ("Graduation Passing", "Graduation Year")),
            ("graduation_percentage", ("Graduation Percentage", "Graduation %")),
            ("graduation_class", ("Graduation Class", "Graduate Class")),
        ):
            v = self._extract_label_value(education, labels)
            if v:
                out[key] = v

        # Other / preferences – from other section, fallback full text
        religion = self._extract_label_value(other, ("Religion", "Religious"))
        if not religion:
            religion = self._extract_label_value(text_clean, ("Religion", "Religious"))
        if religion:
            out["religion"] = religion

        state_applying = self._extract_label_value(
            other,
            ("State Applying For", "State Applying", "State (Applying)"),
        )
        if not state_applying:
            state_applying = self._extract_label_value(
                text_clean,
                ("State Applying For", "State Applying", "State (Applying)"),
            )
        if state_applying:
            out["state_applying_for"] = state_applying

        rrb = self._extract_label_value(other, ("Regional Rural Bank", "RRB", "Bank Name", "Name of RRB"))
        if not rrb:
            rrb = self._extract_label_value(text_clean, ("Regional Rural Bank", "RRB", "Bank Name", "Name of RRB"))
        if rrb:
            out["regional_rural_bank"] = rrb

        exam1 = self._extract_label_value(other, ("Exam Center Preference 1", "Exam Center 1", "Centre Preference 1"))
        if not exam1:
            exam1 = self._extract_label_value(text_clean, ("Exam Center Preference 1", "Exam Center 1", "Centre Preference 1"))
        if exam1:
            out["exam_center_preference1"] = exam1

        exam2 = self._extract_label_value(other, ("Exam Center Preference 2", "Exam Center 2", "Centre Preference 2"))
        if not exam2:
            exam2 = self._extract_label_value(text_clean, ("Exam Center Preference 2", "Exam Center 2", "Centre Preference 2"))
        if exam2:
            out["exam_center_preference2"] = exam2

        medium = self._extract_label_value(other, ("Medium of Paper", "Medium", "Paper Medium"))
        if not medium:
            medium = self._extract_label_value(text_clean, ("Medium of Paper", "Medium", "Paper Medium"))
        if medium:
            out["medium_of_paper"] = medium

        logger.info(f"[ResumeService] Parsed {len(out)} fields from PDF (chunk-by-section, no API)")
        return out

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Normalize line breaks
        text = re.sub(r'\n\s*\n', '\n', text)
        # Trim
        text = text.strip()
        
        return text

