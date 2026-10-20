from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.message import Message
from app.models.audit import MessageEvent
from app.services.message_engine import MessageEngine
from app.adapters.simulation import simulation_adapter
from app.schemas.message import (
    MessageCreate,
    MessageResponse,
    QueueStatsResponse,
    MessageEventResponse,
)

router = APIRouter(tags=["Messaging Engine"])


@router.get("/messages", response_model=List[MessageResponse])
def list_messages(
    sender: Optional[str] = Query(None),
    recipient: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Message)
    if sender:
        query = query.filter_by(sender_endpoint_id=sender)
    if recipient:
        query = query.filter_by(recipient_endpoint_id=recipient)
    if state:
        query = query.filter_by(current_state=state)
    messages = query.order_by(Message.created_at.desc()).all()
    return [m.to_dict() for m in messages]


@router.post("/messages", response_model=MessageResponse)
def submit_message(
    msg_in: MessageCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        msg, is_new = MessageEngine.submit_message(
            session=db,
            client_idempotency_key=msg_in.client_idempotency_key,
            sender_endpoint_id=msg_in.sender_endpoint_id,
            recipient_endpoint_id=msg_in.recipient_endpoint_id,
            payload=msg_in.payload,
            message_type=msg_in.message_type,
            expires_in_seconds=msg_in.expires_in_seconds,
            priority=msg_in.priority,
        )
        response.status_code = status.HTTP_201_CREATED if is_new else status.HTTP_200_OK
        data = msg.to_dict()
        data["is_new"] = is_new
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@router.get("/messages/{message_id}", response_model=MessageResponse)
def get_message(message_id: str, db: Session = Depends(get_db)):
    msg = db.query(Message).filter_by(message_id=message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail=f"Message '{message_id}' not found")
    return msg.to_dict()


@router.get("/messages/{message_id}/events", response_model=List[MessageEventResponse])
def get_message_events(message_id: str, db: Session = Depends(get_db)):
    msg = db.query(Message).filter_by(message_id=message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail=f"Message '{message_id}' not found")
    events = (
        db.query(MessageEvent)
        .filter_by(message_id=message_id)
        .order_by(MessageEvent.timestamp.asc())
        .all()
    )
    return [e.to_dict() for e in events]


@router.post("/messages/{message_id}/retry", response_model=MessageResponse)
def retry_message(message_id: str, db: Session = Depends(get_db)):
    try:
        msg = MessageEngine.retry_message(db, message_id)
        return msg.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/messages/{message_id}/cancel", response_model=MessageResponse)
def cancel_message(message_id: str, db: Session = Depends(get_db)):
    try:
        msg = MessageEngine.cancel_message(db, message_id)
        return msg.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/queue/stats", response_model=QueueStatsResponse)
def queue_stats(db: Session = Depends(get_db)):
    stats = MessageEngine.get_queue_stats(db)
    stats["transport"] = simulation_adapter.get_status()
    return stats
