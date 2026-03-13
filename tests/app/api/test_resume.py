import pytest
import pandas as pd
from io import BytesIO

def test_upload_application_success(client, mock_container_services):
    mock_container_services["resume"].validate_file.return_value = (True, "")
    mock_container_services["booking"].upload_application_to_storage.return_value = "http://storage/resume.pdf"
    mock_container_services["resume"].extract_text.return_value = ("Extracted text", None)
    
    file_content = b"fake pdf content"
    files = {"file": ("resume.pdf", file_content, "application/pdf")}
    
    response = client.post("/api/resume/upload-application", files=files)
    
    assert response.status_code == 200
    assert response.json()["applicationUrl"] == "http://storage/resume.pdf"
    assert response.json()["applicationText"] == "Extracted text"

def test_upload_application_no_file(client):
    response = client.post("/api/resume/upload-application")
    assert response.status_code == 400

def test_upload_application_empty_file(client):
    files = {"file": ("resume.pdf", b"", "application/pdf")}
    response = client.post("/api/resume/upload-application", files=files)
    assert response.status_code == 400
    assert "Uploaded file is empty" in response.json()["detail"]

def test_upload_application_invalid_file(client, mock_container_services):
    mock_container_services["resume"].validate_file.return_value = (False, "Invalid format")
    
    files = {"file": ("resume.pdf", b"invalid", "text/plain")}
    response = client.post("/api/resume/upload-application", files=files)
    
    assert response.status_code == 400
    assert "Invalid format" in response.json()["detail"]

def test_upload_application_storage_failure(client, mock_container_services):
    mock_container_services["resume"].validate_file.return_value = (True, "")
    mock_container_services["booking"].upload_application_to_storage.side_effect = Exception("Storage error")
    
    files = {"file": ("resume.pdf", b"content", "application/pdf")}
    response = client.post("/api/resume/upload-application", files=files)
    
    assert response.status_code == 500
    assert "Failed to upload application" in response.json()["detail"]
