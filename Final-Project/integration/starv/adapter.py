from typing import Dict, List, Any
from integration.base import (
    BaseTransportAdapter,
    TransportReadiness,
    TransportConnectionState,
    utcnow_iso,
)


class StarVSafetyLockoutError(RuntimeError):
    """Raised when an attempt is made to command transmission on the locked-out STAR-V adapter."""
    pass


class StarVAdapter(BaseTransportAdapter):
    """
    STAR-V Tactical Radio Adapter.
    
    Status: PERMANENTLY LOCKED OUT / DISABLED IN SOFTWARE.
    
    Rationale:
    - STAR-V employs classified, proprietary frequency hopping (ECCM) and hardware COMSEC/TRANSEC.
    - Vendor command protocols, serial pinouts, and baud rates are restricted.
    - Direct baseband injection or commanding unauthorized transmission risks severe hardware damage,
      crypto lockout, and statutory telecommunication violations.
    
    Prerequisites to unlock:
    1. Exact radio variant and firmware revision (e.g., STARS-V Mk III).
    2. Authorized Interface Control Document (ICD) and pinout diagram.
    3. Official defense/vendor security authorization for third-party serial/IP data connection.
    4. Valid operational frequency allocation and station license.
    """

    def __init__(self, transport_id: str = "starv-tactical-locked"):
        super().__init__(transport_id, display_name="STAR-V Tactical SDR (LOCKED OUT)")

    @property
    def transport_type(self) -> str:
        return "STARV_TACTICAL_SDR"

    @property
    def supported_operations(self) -> List[str]:
        return []  # Zero operations permitted

    @property
    def readiness(self) -> TransportReadiness:
        return TransportReadiness.LOCKED_OUT

    @property
    def connection_state(self) -> TransportConnectionState:
        return TransportConnectionState.OFFLINE

    def send(self, recipient_endpoint_id: str, payload_bytes: bytes, message_metadata: Dict[str, Any]) -> Dict[str, Any]:
        err = (
            "SAFETY LOCKOUT: STAR-V tactical radio transmission is locked out in software. "
            "No verified interface control document (ICD) or defense authorization is present."
        )
        self.record_error("STARV_SAFETY_LOCKOUT", err)
        return {
            "success": False,
            "error_code": "STARV_SAFETY_LOCKOUT",
            "details": err,
            "delivery_id": None,
        }

    def command_transmit(self, *args: Any, **kwargs: Any) -> None:
        """Hard-command path for direct RF keying.

        This method must NEVER be reachable in normal operation. It exists to
        make the lockout explicit and fatal for any future code path that tries
        to command the radio directly, rather than relying solely on the
        soft ``send()`` refusal above.
        """
        raise StarVSafetyLockoutError(
            "STAR-V direct RF command rejected: adapter is permanently locked out. "
            "Requires official vendor ICD and operational authorization."
        )

    def test_safety_lockout(self, test_type: str = "soft_refusal") -> Dict[str, Any]:
        """Safely test lockout mechanisms without emitting physical RF.

        Supports 'soft_refusal' (via send()) and 'hard_command' (via command_transmit()).
        """
        if test_type == "soft_refusal":
            res = self.send("test-node", b"DRY_RUN_PROBE", {})
            return {
                "status": "BLOCKED",
                "test_type": "soft_refusal",
                "mechanism": "Soft Refusal (send)",
                "error_code": res.get("error_code") or "STARV_SAFETY_LOCKOUT",
                "details": "Software safety lockout refused transmission probe.",
            }
        elif test_type == "hard_command":
            try:
                self.command_transmit()
            except StarVSafetyLockoutError:
                return {
                    "status": "BLOCKED",
                    "test_type": "hard_command",
                    "mechanism": "Hard Exception (command_transmit)",
                    "error_code": "STARV_SAFETY_LOCKOUT_ERROR",
                    "exception_class": "StarVSafetyLockoutError",
                    "details": "Direct RF keying blocked by fatal runtime exception.",
                }
            raise RuntimeError("CRITICAL SAFETY FAULT: STAR-V command_transmit did not raise lockout exception!")
        else:
            raise ValueError(f"Unknown test_type: {test_type}. Must be 'soft_refusal' or 'hard_command'.")

    def health_check(self) -> Dict[str, Any]:
        self.last_health_check_at = utcnow_iso()
        return {
            "transport_id": self.transport_id,
            "display_name": self.display_name,
            "readiness": self.readiness.value,
            "connection_state": self.connection_state.value,
            "safety_lockout": True,
            "lockout_reason": "Classified interface; requires official vendor ICD and operational authorization.",
            "unlocked": False,
        }
