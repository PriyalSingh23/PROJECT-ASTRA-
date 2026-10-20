from typing import Dict, Any, List
from pydantic import BaseModel, Field


class MotorolaDeviceProfile(BaseModel):
    manufacturer: str = "Motorola Solutions"
    product_family: str = Field(..., description="e.g. MOTOTRBO, APX, ASTRO 25, Conventional")
    model_number: str = Field(..., description="Exact model string, e.g. AAH56RDN9WA1AN")
    model_display_name: str
    hardware_revision: str = "Unknown"
    firmware_version: str = "Unknown"
    system_type: str = Field(..., description="ANALOGUE, DMR_DIGITAL, P25_PHASE1, P25_PHASE2")
    interface_type: str = Field(..., description="ACCESSORY_AUDIO_PTT, SERIAL_DATA, IP_GATEWAY")
    supported_capabilities: List[str] = []
    required_vendor_software: str = "None (Hardware GPIO / Audio)"
    deployment_owner: str
    approval_status: str = "APPROVED_FIELD_PILOT"
    test_status: str = "BENCH_VERIFIED"
