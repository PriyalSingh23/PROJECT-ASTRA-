from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class MessageCreate(BaseModel):
    client_idempotency_key: str = Field(..., min_length=1, max_length=128)
    sender_endpoint_id: str = Field(..., min_length=1, max_length=64)
    recipient_endpoint_id: str = Field(..., min_length=1, max_length=64)
    payload: str = Field(..., min_length=1, max_length=65536)
    message_type: str = "TACTICAL_TEXT"
    priority: int = Field(default=2, ge=1, le=5)
    expires_in_seconds: int = Field(default=86400, ge=10)


class MessageResponse(BaseModel):
    message_id: str
    client_idempotency_key: str
    sender_endpoint_id: str
    recipient_endpoint_id: str
    message_type: str
    payload: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    priority: int
    current_state: str
    attempt_count: int
    next_attempt_at: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_at: Optional[str] = None
    accepted_at: Optional[str] = None
    receiver_stored_at: Optional[str] = None
    sender_acknowledged_at: Optional[str] = None
    worker_lease_id: Optional[str] = None
    is_new: Optional[bool] = None

    class Config:
        from_attributes = True


class InboxItemResponse(BaseModel):
    inbox_id: str
    message_id: str
    sender_endpoint_id: str
    recipient_endpoint_id: str
    payload: str
    created_at: Optional[str] = None
    stored_at: Optional[str] = None
    integrity_status: str
    processing_status: str
    current_state: str


class QueueStatsResponse(BaseModel):
    total_messages: int
    pending_message_count: int
    queued: int
    sending: int
    awaiting_ack: int
    delivered: int
    failed_retryable: int
    failed_final: int
    expired: int
    cancelled: int
    last_successful_delivery: Optional[str] = None
    transport: Optional[Dict[str, Any]] = None


class MessageEventResponse(BaseModel):
    event_id: str
    message_id: str
    event_type: str
    timestamp: Optional[str] = None
    source_endpoint: str
    safe_metadata: Dict[str, Any]
    error_code: Optional[str] = None
