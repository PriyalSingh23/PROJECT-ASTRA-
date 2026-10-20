from sqlalchemy import Column, String, Boolean, DateTime
from app.core.database import Base, utcnow


class Endpoint(Base):
    __tablename__ = "endpoints"

    endpoint_id = Column(String(64), primary_key=True)
    display_name = Column(String(128), nullable=False)
    endpoint_type = Column(String(32), default="field_node", nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)

    def to_dict(self):
        return {
            "endpoint_id": self.endpoint_id,
            "display_name": self.display_name,
            "endpoint_type": self.endpoint_type,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
        }
