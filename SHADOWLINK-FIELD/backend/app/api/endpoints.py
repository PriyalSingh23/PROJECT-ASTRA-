from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.core.database import get_db
from app.models.endpoint import Endpoint
from app.services.message_engine import MessageEngine
from app.schemas.message import InboxItemResponse, MessageResponse

router = APIRouter(prefix="/endpoints", tags=["Endpoints & Mailboxes"])


@router.get("", response_model=List[Dict[str, Any]])
def list_endpoints(db: Session = Depends(get_db)):
    endpoints = db.query(Endpoint).all()
    return [e.to_dict() for e in endpoints]


@router.get("/{endpoint_id}/inbox", response_model=List[InboxItemResponse])
def get_endpoint_inbox(endpoint_id: str, db: Session = Depends(get_db)):
    ep = db.query(Endpoint).filter_by(endpoint_id=endpoint_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
    inbox = MessageEngine.get_inbox_messages(db, endpoint_id)
    return inbox


@router.get("/{endpoint_id}/outbox", response_model=List[MessageResponse])
def get_endpoint_outbox(endpoint_id: str, db: Session = Depends(get_db)):
    ep = db.query(Endpoint).filter_by(endpoint_id=endpoint_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
    outbox = MessageEngine.get_outbox_messages(db, endpoint_id)
    return outbox
