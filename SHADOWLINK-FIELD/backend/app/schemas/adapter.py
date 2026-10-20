from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class SimTransportUpdate(BaseModel):
    is_online: Optional[bool] = None
    latency_ms: Optional[float] = None
    drop_message_prob: Optional[float] = None
    drop_ack_prob: Optional[float] = None
    reset: Optional[bool] = None


class FaultInjectionRequest(BaseModel):
    message_id: str
    action: str  # drop_message, drop_ack, error
    error_code: Optional[str] = "TEMPORARY_NETWORK_ERROR"


class AdapterMetadataResponse(BaseModel):
    adapter_id: str
    name: str
    vendor: str
    version: str
    category: str
    is_hardware: bool
    status: str
    capabilities: List[str]
