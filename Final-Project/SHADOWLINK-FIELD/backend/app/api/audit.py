from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.core.database import get_db
from app.core.security import require_role, UserRole
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit & Event Logs"])


@router.get("/logs", response_model=List[Dict[str, Any]])
def get_audit_logs(
    action: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
    _=Depends(require_role([UserRole.ADMIN, UserRole.OPERATOR])),
):
    return AuditService.get_logs(db, action=action, user_id=user_id, limit=limit)
