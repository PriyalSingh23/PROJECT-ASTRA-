import shutil
import platform
from typing import Dict, Any, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import utcnow
from app.services.gateway_router import gateway_router
from app.schemas.diagnostic import ComponentHealth, DiagnosticReport


class DiagnosticService:
    """Non-transmitting diagnostic service verifying system readiness."""

    @classmethod
    async def run_full_diagnostics(cls, session: Session) -> DiagnosticReport:
        components: List[ComponentHealth] = []
        overall_ok = True

        # 1. Database Check
        try:
            session.execute(text("SELECT 1")).scalar()
            components.append(ComponentHealth(component="database", status="HEALTHY", details={"dialect": "sqlite/wal"}))
        except Exception as e:
            overall_ok = False
            components.append(ComponentHealth(component="database", status="DOWN", details={"error": str(e)}))

        # 2. Disk Storage Check
        try:
            total, used, free = shutil.disk_usage("/")
            free_gb = round(free / (1024 ** 3), 2)
            disk_status = "HEALTHY" if free_gb > 1.0 else "WARNING"
            components.append(
                ComponentHealth(
                    component="storage",
                    status=disk_status,
                    details={"free_gb": free_gb, "total_gb": round(total / (1024 ** 3), 2)},
                )
            )
        except Exception as e:
            components.append(ComponentHealth(component="storage", status="DEGRADED", details={"error": str(e)}))

        # 3. Adapter Health Checks
        active_transports = []
        for adapter in gateway_router.list_adapters():
            meta = adapter.get_metadata()
            try:
                report = await adapter.check_health()
                comp_status = "HEALTHY"
                if report.state.value == "OFFLINE":
                    comp_status = "DEGRADED"
                elif report.state.value == "DISABLED_PREREQUISITES_MISSING":
                    comp_status = "DISABLED"

                components.append(
                    ComponentHealth(
                        component=f"adapter:{meta.adapter_id}",
                        status=comp_status,
                        details={
                            "name": meta.name,
                            "state": report.state.value,
                            "ready": report.ready_to_transmit,
                            "summary": report.summary,
                        },
                    )
                )
                if report.ready_to_transmit or "SIMULATION" in report.state.value:
                    active_transports.append(meta.adapter_id)
            except Exception as e:
                components.append(
                    ComponentHealth(
                        component=f"adapter:{meta.adapter_id}",
                        status="DEGRADED",
                        details={"error": str(e)},
                    )
                )

        sys_status = "HEALTHY" if overall_ok else "CRITICAL"
        return DiagnosticReport(
            system_status=sys_status,
            timestamp=utcnow().isoformat(),
            environment=f"{platform.system()} {platform.release()} ({platform.machine()})",
            database_ok=overall_ok,
            queue_ok=True,
            components=components,
            active_transports=active_transports,
            system_load={"python_version": platform.python_version()},
        )
