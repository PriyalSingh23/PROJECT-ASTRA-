from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class DeviceProfileCreate(BaseModel):
    display_name: str
    manufacturer: str
    product_family: str
    model_number: str
    hardware_revision: Optional[str] = None
    firmware_version: Optional[str] = None
    system_type: str
    interface_type: str
    supported_capabilities: List[str]
    approval_status: str = "UNVERIFIED"
    test_status: str = "UNTESTED"


class DeviceProfileResponse(DeviceProfileCreate):
    device_id: str
    enabled: bool
    created_at: Optional[str] = None
    last_verified_at: Optional[str] = None

    class Config:
        from_attributes = True
