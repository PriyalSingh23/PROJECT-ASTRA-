import uuid
from sqlalchemy import Column, String, DateTime, JSON, Text
from app.core.database import Base, utcnow


class ExperimentRecord(Base):
    __tablename__ = "experiment_records"

    experiment_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False)
    software_revision = Column(String(64), default="1.0.0", nullable=False)
    test_type = Column(String(64), nullable=False)  # e.g., "EW_8_DOMAIN", "BER_SNR_SWEEP", "FIELD_SYNC_TEST"
    configuration_version = Column(String(64), nullable=False)
    model_checkpoint = Column(String(128), nullable=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    metrics = Column(JSON, default=dict, nullable=False)
    status = Column(String(32), default="RUNNING", nullable=False)  # RUNNING, PASSED, FAILED
    reviewer_notes = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "software_revision": self.software_revision,
            "test_type": self.test_type,
            "configuration_version": self.configuration_version,
            "model_checkpoint": self.model_checkpoint,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metrics": self.metrics,
            "status": self.status,
            "reviewer_notes": self.reviewer_notes,
        }
