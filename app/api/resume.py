from fastapi import APIRouter, HTTPException, UploadFile, File, status

from app.schemas.resume import UploadApplicationResponse
from app.services.container import (
    resume_service,
    booking_service,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Resume / application upload endpoints
router = APIRouter(tags=["Resume"])


@router.post("/upload-application", response_model=UploadApplicationResponse)
async def upload_application(file: UploadFile = File(...)):
    """
    Upload and process application file.

    Extracts text from PDF or DOC/DOCX files and uploads to storage.
    """
    try:
        # Handle case where file might be None or empty
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        logger.info(f"[API] Received application upload: {file.filename} ({file.content_type})")

        # Read file content
        file_content = await file.read()

        # Check if file is empty
        if not file_content or len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty"
            )

        # Validate file
        is_valid, error_msg = resume_service.validate_file(
            file_content, file.filename, file.content_type
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        # Upload to storage
        try:
            application_url = booking_service.upload_application_to_storage(file_content, file.filename)
        except Exception as e:
            logger.error(f"[API] Failed to upload to storage: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload application: {str(e)}"
            )

        # Extract text
        application_text, extraction_error = resume_service.extract_text(
            file_content, file.filename, file.content_type
        )

        if application_text:
            logger.info(f"[API] ✅ Application processed: {len(application_text)} characters extracted")
        else:
            logger.warning(f"[API] ⚠️ Application uploaded but text extraction failed: {extraction_error}")

        return UploadApplicationResponse(
            applicationUrl=application_url,
            applicationText=application_text if application_text else None,
            extractionError=extraction_error,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to process application: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        # Return more detailed error for debugging
        if "422" in str(e) or "Unprocessable" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file format or file is corrupted. Please ensure the file is a valid PDF, DOC, or DOCX file."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


