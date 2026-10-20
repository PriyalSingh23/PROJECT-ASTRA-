from pydantic import BaseModel
from typing import Dict, Any, List, Optional


class ComponentHealth(BaseModel):
    component: str
    status: str  # HEALTHY, DEGRADED, DOWN, DISABLED
    details: Optional[Dict[str, Any]] = None


class DiagnosticReport(BaseModel):
    system_status: str  # HEALTHY, WARNING, CRITICAL
    timestamp: str
    environment: str
    database_ok: bool
    queue_ok: bool
    components: List[ComponentHealth]
    active_transports: List[str]
    system_load: Optional[Dict[str, Any]] = None
