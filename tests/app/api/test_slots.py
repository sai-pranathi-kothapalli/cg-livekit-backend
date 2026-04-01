import pytest
from datetime import datetime

def test_create_slot(client, mock_container_services, mock_admin_auth):
    mock_container_services["slot"].get_slot_by_datetime.return_value = None
    mock_container_services["slot"].create_slot.return_value = {
        "id": "slot-1",
        "slot_datetime": "2026-03-15T10:00:00+05:30",
        "duration_minutes": 30,
        "max_capacity": 10,
        "current_bookings": 0,
        "status": "active",
        "created_at": "2026-03-13T10:00:00Z"
    }
    
    response = client.post("/api/slots/admin/slots", json={
        "slot_datetime": "2026-03-15T10:00:00+05:30",
        "max_capacity": 10,
        "duration_minutes": 30
    })
    
    assert response.status_code == 200
    assert response.json()["id"] == "slot-1"

def test_get_all_slots_admin(client, mock_container_services, mock_admin_auth):
    mock_container_services["slot"].get_all_slots.return_value = [
        {
            "id": "slot-1",
            "slot_datetime": "2026-03-15T10:00:00+05:30",
            "duration_minutes": 30,
            "max_capacity": 10,
            "current_bookings": 0,
            "status": "active",
            "created_at": "2026-03-13T10:00:00Z"
        }
    ]
    
    response = client.get("/api/slots/admin/slots")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_get_slot(client, mock_container_services, mock_admin_auth):
    mock_container_services["slot"].get_slot.return_value = {
        "id": "slot-1",
        "slot_datetime": "2026-03-15T10:00:00+05:30",
        "duration_minutes": 30,
        "max_capacity": 10,
        "current_bookings": 0,
        "status": "active",
        "created_at": "2026-03-13T10:00:00Z"
    }
    
    response = client.get("/api/slots/admin/slots/slot-1")
    assert response.status_code == 200
    assert response.json()["id"] == "slot-1"

def test_update_slot(client, mock_container_services, mock_admin_auth):
    mock_container_services["slot"].update_slot.return_value = {
        "id": "slot-1",
        "slot_datetime": "2026-03-15T10:00:00+05:30",
        "duration_minutes": 30,
        "max_capacity": 20,
        "current_bookings": 0,
        "status": "active",
        "created_at": "2026-03-13T10:00:00Z"
    }
    
    response = client.put("/api/slots/admin/slots/slot-1", json={"max_capacity": 20})
    assert response.status_code == 200
    assert response.json()["max_capacity"] == 20

def test_delete_slot(client, mock_container_services, mock_admin_auth):
    response = client.delete("/api/slots/admin/slots/slot-1")
    assert response.status_code == 200

def test_get_available_slots_public(client, mock_container_services):
    mock_container_services["slot"].get_available_slots.return_value = [
        {
            "id": "slot-1",
            "slot_datetime": "2026-03-15T10:00:00+05:30",
            "duration_minutes": 30,
            "max_capacity": 10,
            "current_bookings": 0,
            "status": "active",
            "created_at": "2026-03-13T10:00:00Z"
        }
    ]
    
    response = client.get("/api/slots/available")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_create_day_slots(client, mock_container_services, mock_admin_auth):
    # create_day_slots returns (List[Dict], List[str])
    mock_container_services["slot"].create_day_slots.return_value = ([
        {
            "id": "slot-1",
            "slot_datetime": "2026-03-15T10:00:00+05:30",
            "duration_minutes": 30,
            "max_capacity": 10,
            "current_bookings": 0,
            "status": "active",
            "created_at": "2026-03-13T10:00:00Z"
        }
    ], [])
    
    response = client.post("/api/slots/admin/slots/create-day", json={
        "date": "2026-03-15",
        "start_time": "10:00",
        "end_time": "12:00",
        "interval_minutes": 30,
        "max_capacity": 10
    })
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(response.json()["slots"]) == 1
