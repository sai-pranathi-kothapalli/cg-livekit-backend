import pytest
from io import BytesIO
import pandas as pd
import urllib.parse

def test_enroll_user_success(client, mock_container_services, mock_admin_auth):
    mock_container_services["auth"].generate_temporary_password.return_value = "temp123"
    mock_container_services["auth"].register_student.return_value = {"id": "s1"}
    mock_container_services["user"].create_user.return_value = {
        "id": "u1",
        "email": "test@example.com",
        "name": "Test User",
        "status": "enrolled",
        "created_at": "2026-03-13T10:00:00Z"
    }
    
    response = client.post("/api/users/", json={
        "name": "Test",
        "email": "test@example.com",
        "slot_ids": []
    })
    
    assert response.status_code == 200
    assert response.json()["id"] == "u1"

def test_bulk_enroll_users(client, mock_container_services, mock_admin_auth):
    # Create a mock Excel file
    df = pd.DataFrame([{"name": "U1", "email": "u1@example.com"}])
    excel_file = BytesIO()
    df.to_excel(excel_file, index=False)
    excel_file.seek(0)
    
    mock_container_services["auth"].generate_temporary_password.return_value = "pass"
    mock_container_services["user"].create_user.return_value = {
        "id": "u1",
        "email": "u1@example.com",
        "name": "U1",
        "status": "enrolled",
        "created_at": "2026-03-13T10:00:00Z"
    }
    
    files = {"file": ("users.xlsx", excel_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    response = client.post("/api/users/bulk-enroll", files=files)
    
    assert response.status_code == 200
    assert response.json()["successful"] == 1

def test_get_all_users(client, mock_container_services, mock_admin_auth):
    mock_container_services["user"].get_all_users.return_value = [{
        "id": "u1",
        "email": "u1@example.com",
        "name": "U1",
        "status": "enrolled",
        "created_at": "2026-03-13T10:00:00Z"
    }]
    
    response = client.get("/api/users/")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_get_user_detail(client, mock_container_services, mock_admin_auth):
    mock_container_services["user"].get_user.return_value = {
        "id": "u1",
        "email": "u1@example.com",
        "name": "U1",
        "status": "enrolled",
        "created_at": "2026-03-13T10:00:00Z"
    }
    mock_container_services["booking"].get_user_bookings.return_value = []
    mock_container_services["evaluation"].get_evaluations_for_bookings.return_value = []
    # analytics mock
    mock_container_services["evaluation"].get_student_analytics.return_value = {"overall_analysis": "good"}
    
    response = client.get("/api/users/u1")
    assert response.status_code == 200
    assert response.json()["id"] == "u1"

def test_update_user(client, mock_container_services, mock_admin_auth):
    mock_container_services["user"].update_user.return_value = {
        "id": "u1",
        "email": "u1@example.com",
        "name": "Updated",
        "status": "enrolled",
        "created_at": "2026-03-13T10:00:00Z"
    }
    
    response = client.put("/api/users/u1", json={"name": "Updated"})
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"

def test_delete_user(client, mock_container_services, mock_admin_auth):
    mock_container_services["user"].get_user.return_value = {"id": "u1", "email": "u1@example.com"}
    mock_container_services["booking"].get_bookings_by_user_id.return_value = []
    
    response = client.delete("/api/users/u1")
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_remove_student_auth(client, mock_container_services, mock_admin_auth):
    mock_container_services["admin"].delete_student_account_by_email.return_value = True
    
    # UserResponse used as input; requires id, name, email, status, created_at
    payload = {
        "id": "u1",
        "name": "Test",
        "email": "test@example.com",
        "status": "enrolled",
        "created_at": "2026-03-13T10:00:00Z"
    }
    response = client.post("/api/users/remove-student-auth", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is True
