import pytest
from app.services import container
from app.services.admin_service import AdminService
from app.services.user_service import UserService

def test_container_instances():
    # Verify that services are initialized and available
    assert isinstance(container.admin_service, AdminService)
    assert isinstance(container.user_service, UserService)
    assert container.config is not None
