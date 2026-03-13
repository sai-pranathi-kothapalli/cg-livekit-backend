import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO
import pandas as pd

def test_get_job_description(client, mock_admin_auth, mock_container_services):
    mock_container_services["system_instructions"].get_system_instructions.return_value = {"instructions": "Test JD"}
    
    response = client.get("/api/admin/job-description")
    
    assert response.status_code == 200
    assert response.json() == {"context": "Test JD"}
    mock_container_services["system_instructions"].get_system_instructions.assert_called_once()

def test_update_job_description(client, mock_admin_auth, mock_container_services):
    mock_container_services["system_instructions"].update_system_instructions.return_value = {"instructions": "Updated JD"}
    
    response = client.put("/api/admin/job-description", json={"context": "Updated JD"})
    
    assert response.status_code == 200
    assert response.json() == {"context": "Updated JD"}
    mock_container_services["system_instructions"].update_system_instructions.assert_called_once_with(instructions="Updated JD")

def test_enroll_manager(client, mock_admin_auth, mock_container_services):
    mock_container_services["auth"].register_manager.return_value = {
        "id": "mgr-1",
        "username": "mgr1",
        "email": "mgr1@example.com",
        "name": "Manager 1",
        "role": "manager",
        "created_at": "2023-01-01"
    }
    
    response = client.post("/api/admin/managers", json={"name": "Manager 1", "email": "mgr1@example.com"})
    
    assert response.status_code == 200
    assert response.json()["email"] == "mgr1@example.com"
    assert response.json()["role"] == "manager"

def test_list_managers(client, mock_admin_auth):
    with patch("app.api.admin.get_supabase") as mock_supabase:
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[
            {"id": "mgr-1", "email": "mgr1@example.com", "role": "manager", "name": "Mgr 1"}
        ])
        
        response = client.get("/api/admin/managers")
        
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["email"] == "mgr1@example.com"

def test_delete_manager(client, mock_admin_auth):
    with patch("app.api.admin.get_supabase") as mock_supabase:
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        
        response = client.delete("/api/admin/managers/mgr-1")
        
        assert response.status_code == 200
        assert response.json() == {"success": True, "message": "Manager mgr-1 deleted"}
        mock_client.table.assert_called_with("users")

def test_register_candidate(client, mock_admin_auth, mock_container_services):
    mock_container_services["booking"].create_booking.return_value = "test-token"
    mock_container_services["email"].send_interview_email.return_value = (True, None)
    
    response = client.post("/api/admin/register-candidate", json={
        "name": "Candidate",
        "email": "c@example.com",
        "phone": "1234567890",
        "datetime": "2026-12-31T10:00:00"
    })
    
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "interview/test-token" in response.json()["interviewUrl"]

def test_bulk_register(client, mock_admin_auth, mock_container_services):
    # Create a mock Excel file
    df = pd.DataFrame([
        {"name": "C1", "email": "c1@example.com", "phone": "1", "datetime": "2026-12-31T10:00:00"},
        {"name": "C2", "email": "c2@example.com", "phone": "2", "datetime": "2026-12-31T11:00:00"}
    ])
    excel_file = BytesIO()
    df.to_excel(excel_file, index=False)
    excel_file.seek(0)
    
    mock_container_services["booking"].create_booking.return_value = "token"
    mock_container_services["email"].send_interview_email.return_value = (True, None)
    
    response = client.post("/api/admin/bulk-register", files={
        "file": ("test.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    })
    
    assert response.status_code == 200
    assert response.json()["successful"] == 2
    assert response.json()["total"] == 2
