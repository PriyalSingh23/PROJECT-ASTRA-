from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from app.services.gateway_router import gateway_router
from app.adapters.simulation import simulation_adapter
from app.schemas.adapter import (
    AdapterMetadataResponse,
    SimTransportUpdate,
    FaultInjectionRequest,
)

router = APIRouter(tags=["Adapters & Transport Routing"])


@router.get("/adapters", response_model=List[AdapterMetadataResponse])
def list_adapters():
    result = []
    for adapter in gateway_router.list_adapters():
        meta = adapter.get_metadata()
        caps = [c.value for c in adapter.get_capabilities()]
        result.append(
            AdapterMetadataResponse(
                adapter_id=meta.adapter_id,
                name=meta.name,
                vendor=meta.vendor,
                version=meta.version,
                category=meta.category,
                is_hardware=meta.is_hardware,
                status="ONLINE" if ("sim" in meta.adapter_id or "motorola" in meta.adapter_id) else "DISABLED",
                capabilities=caps,
            )
        )
    return result


@router.get("/sim/transport", response_model=Dict[str, Any])
def get_sim_transport():
    return simulation_adapter.get_status()


@router.post("/sim/transport", response_model=Dict[str, Any])
async def update_sim_transport(update: SimTransportUpdate):
    config = update.model_dump(exclude_unset=True)
    return await simulation_adapter.validate_config(config)


@router.post("/sim/faults")
def inject_sim_fault(req: FaultInjectionRequest):
    if req.action == "drop_message":
        simulation_adapter.dropped_messages.add(req.message_id)
    elif req.action == "drop_ack":
        simulation_adapter.dropped_acks.add(req.message_id)
    elif req.action == "error":
        simulation_adapter.injected_faults[req.message_id] = req.error_code or "TEMPORARY_NETWORK_ERROR"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown fault action: {req.action}")

    return {
        "status": "fault_injected",
        "message_id": req.message_id,
        "action": req.action,
    }
