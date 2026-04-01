import pytest
from pydantic import ValidationError
from app.schemas.resume import UploadApplicationResponse

def test_upload_application_response():
    valid_data = {
        "applicationUrl": "http://example.com/res.pdf",
        "applicationText": "Extracted text"
    }
    model = UploadApplicationResponse(**valid_data)
    assert model.applicationUrl == "http://example.com/res.pdf"
    assert model.extractionError is None
    
    with pytest.raises(ValidationError):
        UploadApplicationResponse()
