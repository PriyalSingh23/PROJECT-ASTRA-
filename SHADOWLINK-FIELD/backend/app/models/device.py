import uuid
from sqlalchemy import Column, String, Boolean, DateTime, JSON
from app.core.database import Base, utcnow


class DeviceProfile(Base):
    __tablename__ = "device_profiles"

    device_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name = Column(String(128), nullable=False)
    manufacturer = Column(String(64), nullable=False)  # e.g. Motorola Solutions, BEL, Ettus Research
    product_family = Column(String(64), nullable=False)  # e.g. MOTOTRBO, STAR-V, USRP
    model_number = Column(String(64), nullable=False)
    hardware_revision = Column(String(64), nullable=True)
    firmware_version = Column(String(64), nullable=True)
    system_type = Column(String(32), nullable=False)  # ANALOGUE, DMR_DIGITAL, P25, SDR_RESEARCH
    interface_type = Column(String(64), nullable=False)  # ACCESSORY_AUDIO_PTT, SERIAL_DATA, IP_GATEWAY, UHD
    supported_capabilities = Column(JSON, default=list, nullable=False)
    approval_status = Column(String(32), default="UNVERIFIED", nullable=False)
    test_status = Column(String(32), default="UNTESTED", nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_verified_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "device_id": self.device_id,
            "display_name": self.display_name,
            "manufacturer": self.manufacturer,
            "product_family": self.product_family,
            "model_number": self.model_number,
            "hardware_revision": self.hardware_revision,
            "firmware_version": self.firmware_version,
            "system_type": self.system_type,
            "interface_type": self.interface_type,
            "supported_capabilities": self.supported_capabilities,
            "approval_status": self.approval_status,
            "test_status": self.test_status,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None,
        }
