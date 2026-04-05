import pytest
from datetime import datetime, timezone
from backend.app.models.admin_audit_log import AdminAuditLog

def test_admin_audit_log_instantiation():
    """Test that AdminAuditLog model instantiates correctly with required fields."""
    log = AdminAuditLog(
        admin_user_id=1,
        action="user.update",
        target_type="user",
        target_id="123",
        before_state={"is_active": True},
        after_state={"is_active": False},
        context={"source": "admin_api"}
    )
    
    assert log.admin_user_id == 1
    assert log.action == "user.update"
    assert log.target_type == "user"
    assert log.target_id == "123"
    assert log.before_state == {"is_active": True}
    assert log.after_state == {"is_active": False}
    assert log.context == {"source": "admin_api"}

def test_admin_audit_log_defaults():
    """Test that AdminAuditLog model handles defaults correctly."""
    log = AdminAuditLog(
        action="system.login",
        target_type="system"
    )
    
    assert log.action == "system.login"
    assert log.target_type == "system"
    assert log.admin_user_id is None
    assert log.target_id is None
    assert log.before_state is None
    assert log.after_state is None
    assert log.context is None
