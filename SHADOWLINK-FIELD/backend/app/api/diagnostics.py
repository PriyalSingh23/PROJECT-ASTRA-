from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.diagnostic_service import DiagnosticService
from app.schemas.diagnostic import DiagnosticReport

router = APIRouter(prefix="/diagnostics", tags=["System Diagnostics"])


@router.get("", response_model=DiagnosticReport)
async def get_diagnostics(db: Session = Depends(get_db)):
    return await DiagnosticService.run_full_diagnostics(db)


@router.get("/health")
def health_check():
    return {
        "status": "HEALTHY",
        "service": "shadowlink-field-core",
        "version": "1.0.0",
        "mode": "FIELD_OPERATIONS",
    }
