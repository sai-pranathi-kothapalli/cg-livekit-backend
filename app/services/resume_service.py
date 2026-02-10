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
    
    def _normalize_spacing(self, text: str) -> str:
        """
        Fix spacing issues from PyPDF2 (e.g., 'Sc ale-I' -> 'Scale-I', 'HUSS AIN' -> 'HUSSAIN').
        """
        if not text:
            return text
        
        # Remove spaces within words (common PyPDF2 artifact)
        # Pattern: letter + space + lowercase letter (e.g., "Sc ale" -> "Scale")
        text = re.sub(r'([a-z])\s+([a-z])', r'\1\2', text, flags=re.IGNORECASE)
        
        # Remove spaces within uppercase words (e.g., "HUSS AIN" -> "HUSSAIN")
        text = re.sub(r'([A-Z])\s+([A-Z])', r'\1\2', text)
        
        # Remove spaces around hyphens (e.g., "Scale- I" -> "Scale-I")
        text = re.sub(r'\s*-\s*', '-', text)
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _clean_extracted_value(self, value: str) -> str:
        """
        Clean up extracted value by removing common label contamination and artifacts.
        """
        if not value:
            return value
        
        # Remove common label patterns that got captured
        # Pattern: "Card Number :XXXXXXXX" -> "XXXXXXXX"
        value = re.sub(r'^.*?(?:Card\s+Number|Number)\s*:?\s*', '', value, flags=re.IGNORECASE)
        
        # Remove trailing label patterns (e.g., "'s Name :" at end)
        value = re.sub(r"'s\s+Name\s*:?\s*$", '', value, flags=re.IGNORECASE)
        
        # Remove question-like patterns (more aggressive)
        value = re.sub(r'\s*-?\s*ho?w?\s+y?ou\s+w?ould.*$', '', value, flags=re.IGNORECASE)
        value = re.sub(r'\s*-?\s*of\s*P?\s*aper.*$', '', value, flags=re.IGNORECASE)
        value = re.sub(r't?\s*o\s+which\s+y?\s*ou\s+belong\s*:?', '', value, flags=re.IGNORECASE)
        
        # Remove common incomplete fragments (only if they're the ENTIRE value)
        if re.match(r'^(ress|s \(CRP)$', value, flags=re.IGNORECASE):
            return ''
        
        # Fix "Bachelorof" -> "Bachelor of" spacing (but don't remove if it's the whole value)
        value = re.sub(r'(Bachelor|Master|Diploma)(of)', r'\1 \2', value, flags=re.IGNORECASE)
        
        # Remove "code :" prefix from pincodes
        value = re.sub(r'^code\s*:?\s*', '', value, flags=re.IGNORECASE)
        
        # Remove leading/trailing colons, dashes, and extra punctuation
        value = value.strip(':- .')
        
        # Normalize spacing
        value = self._normalize_spacing(value)
        
        # Remove any remaining single letters or very short fragments at start
        value = re.sub(r'^[a-z]\s+', '', value, flags=re.IGNORECASE)
        
        return value.strip()
    
    def _extract_phone_number(self, text: str) -> Optional[str]:
        """
        Extract phone number from text, handling various formats and spacing issues.
        """
        # Look for patterns like "91 630290 7829" or "9163029078 29" or "9163029078" 
        # Remove all spaces first, then extract 10-12 digit numbers
        text_no_spaces = re.sub(r'\s+', '', text)
        
        # Pattern: optional +91 or 91, followed by 10 digits
        phone_match = re.search(r'(?:\+?91)?([6-9]\d{9})', text_no_spaces)
        if phone_match:
            return phone_match.group(1)  # Return just the 10-digit number
        
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """
        Extract date from text and normalize to YYYY-MM-DD format.
        """
        # Remove spacing issues first
        text = self._normalize_spacing(text)
        
        # Skip if text is just a slash or very short
        if not text or len(text.strip()) <= 1 or text.strip() == '/':
            return None
        
        # Try various date patterns
        patterns = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # DD/MM/YYYY or DD-MM-YYYY
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # YYYY/MM/DD or YYYY-MM-DD
            r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})',  # DD Month YYYY
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                parts = match.groups()
                
                # Handle month name format
                if len(parts) == 3 and not parts[1].isdigit():
                    day, month_name, year = parts
                    month_map = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
                    month = month_map.get(month_name[:3].lower(), 0)
                    if month == 0:
                        continue
                    day = int(day)
                    year = int(year)
                # Try to determine format and convert to YYYY-MM-DD
                elif len(parts[0]) == 4:  # YYYY-MM-DD format
                    year, month, day = parts
                    day = int(day)
                    month = int(month)
                    year = int(year)
                else:  # DD-MM-YYYY format (common in India)
                    day, month, year = parts
                    day = int(day)
                    month = int(month)
                    year = int(year)
                
                try:
                    # Validate and format
                    if 1 <= day <= 31 and 1 <= month <= 12:
                        return f"{year:04d}-{month:02d}-{day:02d}"
                except (ValueError, UnboundLocalError):
                    continue
        
        return None
    
    def _extract_aadhaar(self, text: str) -> Optional[str]:
        """
        Extract Aadhaar number and remove spacing issues.
        """
        # Remove all spaces first
        text_no_spaces = re.sub(r'\s+', '', text)
        
        # Look for 12-digit Aadhaar (may be masked with X's)
        aadhaar_match = re.search(r'([X\d]{12})', text_no_spaces, flags=re.IGNORECASE)
        if aadhaar_match:
            return aadhaar_match.group(1)
        
        return None

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
                # Clean the extracted value
                val = self._clean_extracted_value(val)
                if val and val.lower() not in ("-", "na", "n/a", "nil", "—", "–", ":"):
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
                # Clean the extracted value
                val = self._clean_extracted_value(val)
                if val and val.lower() not in ("-", "na", "n/a", "nil", "—", "–", ":"):
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
        Parse extracted text into structured application data using regex/heuristics.
        Chunks text by section first, then extracts each field from the relevant section.
        """
        if not text or len(text.strip()) < 10:
            return {}
        
        # Clean but preserve newlines for better structure
        text_clean = self._clean_text(text)
        logger.info("[ResumeService] Using regex-based parsing")
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
            # Use specialized date extractor
            extracted_date = self._extract_date(dob_raw)
            out["date_of_birth"] = extracted_date if extracted_date else dob_raw

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
            # Use specialized Aadhaar extractor to remove spacing
            extracted_aadhaar = self._extract_aadhaar(aadhaar)
            out["aadhaar_number"] = extracted_aadhaar if extracted_aadhaar else aadhaar.strip()

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

        # Permanent address – from permanent section or full text fallback
        for key, labels in (
            ("permanent_address1", ("Permanent Address", "Permanent Add", "Address Line 1", "Permanent Addr", "P Address")),
            ("permanent_state", ("Permanent State", "State")),
            ("permanent_district", ("Permanent District", "District")),
            ("permanent_pincode", ("Permanent Pincode", "Permanent Pin", "Pin")),
        ):
            v = self._extract_label_value(perm_addr, labels)
            # Fallback to full text if not found in section
            if not v:
                v = self._extract_label_value(text_clean, labels)
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
            # Use specialized phone extractor to clean up spacing
            extracted_phone = self._extract_phone_number(mobile)
            out["mobile_number"] = extracted_phone if extracted_phone else mobile.strip()

        # Education – from education section only
        for key, labels in (
            ("ssc_board", ("SSC Board", "10th Board", "Board (SSC)", "Board")),
            ("ssc_passing_date", ("SSC Passing", "SSC Year", "10th Passing", "SSC Passing Year")),
            ("ssc_percentage", ("SSC Percentage", "SSC %", "10th Percentage", "SSC Marks")),
            ("ssc_class", ("SSC Class", "10th Class", "SSC Division")),
            ("graduation_degree", ("Graduation Degree", "Degree", "Graduate Degree", "Qualification", "Educational Qualification")),
            ("graduation_college", ("Graduation College", "College", "Graduate College", "College Name", "University")),
            ("graduation_specialization", ("Specialization", "Graduation Specialization", "Stream", "Subject")),
            ("graduation_passing_date", ("Graduation Passing", "Graduation Year", "Passing Year")),
            ("graduation_percentage", ("Graduation Percentage", "Graduation %", "Graduation Marks")),
            ("graduation_class", ("Graduation Class", "Graduate Class", "Division")),
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

    def save_extracted_data_to_json(self, data: Dict[str, Any], original_filename: str) -> str:
        """
        Save extracted data to a JSON file in the extracted_pdfs folder.
        Returns the absolute path to the saved file.
        """
        import json
        import os
        from pathlib import Path
        from datetime import datetime
        
        # Create extracted_pdfs directory if it doesn't exist
        backend_dir = Path(__file__).resolve().parent.parent.parent
        output_dir = backend_dir / "extracted_pdfs"
        output_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(original_filename).stem
        json_filename = f"{timestamp}_{base_name}.json"
        json_path = output_dir / json_filename
        
        # Save JSON file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[ResumeService] 💾 Saved extracted data to: {json_path}")
        return str(json_path)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text while preserving structure"""
        # Remove null characters
        text = text.replace('\0', '')
        # Normalize multiple spaces to single but keep newlines
        text = re.sub(r'[ \t]+', ' ', text)
        # Normalize excessive newlines
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        return text.strip()

