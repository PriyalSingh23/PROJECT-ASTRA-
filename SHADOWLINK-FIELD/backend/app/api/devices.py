from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db, utcnow
from app.core.security import require_role, UserRole
from app.models.device import DeviceProfile
from app.schemas.device import DeviceProfileCreate, DeviceProfileResponse

router = APIRouter(prefix="/devices", tags=["Device Management"])


@router.get("", response_model=List[DeviceProfileResponse])
def list_devices(db: Session = Depends(get_db)):
    devices = db.query(DeviceProfile).all()
    return devices


@router.post("", response_model=DeviceProfileResponse, status_code=status.HTTP_201_CREATED)
def register_device(
    device_in: DeviceProfileCreate,
    db: Session = Depends(get_db),
    _=Depends(require_role([UserRole.ADMIN])),
):
    dev = DeviceProfile(
        display_name=device_in.display_name,
        manufacturer=device_in.manufacturer,
        product_family=device_in.product_family,
        model_number=device_in.model_number,
        hardware_revision=device_in.hardware_revision,
        firmware_version=device_in.firmware_version,
        system_type=device_in.system_type,
        interface_type=device_in.interface_type,
        supported_capabilities=device_in.supported_capabilities,
        approval_status=device_in.approval_status,
        test_status=device_in.test_status,
        enabled=True,
        created_at=utcnow(),
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev
