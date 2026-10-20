import time
import random
from typing import Dict, Any, Optional, Set


class SimulatedTransport:
    """Simulated transport layer between Endpoint A and Endpoint B.
    
    Provides deliberate fault-injection capabilities:
      - Online/offline toggling
      - Artificial latency injection
      - Statistical packet/ACK dropping
      - Deterministic message/ACK dropping for automated testing
    """
    PRESETS = {
        "NOMINAL": {"is_online": True, "latency_ms": 0.0, "drop_message_prob": 0.0, "drop_ack_prob": 0.0},
        "URBAN_JAMMING": {"is_online": True, "latency_ms": 50.0, "drop_message_prob": 0.3, "drop_ack_prob": 0.1},
        "AIR_GAP": {"is_online": False, "latency_ms": 0.0, "drop_message_prob": 1.0, "drop_ack_prob": 1.0},
        "SATELLITE": {"is_online": True, "latency_ms": 800.0, "drop_message_prob": 0.05, "drop_ack_prob": 0.05},
    }

    _instance: Optional["SimulatedTransport"] = None

    def __init__(self):
        self.is_online: bool = True
        self.latency_ms: float = 0.0
        self.drop_message_prob: float = 0.0
        self.drop_ack_prob: float = 0.0

        # Armed single-shot faults (auto-disarming on trigger)
        self.arm_drop_next_message: bool = False
        self.arm_drop_next_ack: bool = False
        self.arm_corrupt_next_hmac: bool = False
        self.active_preset: str = "NOMINAL"

        # Deterministic test sets
        self.deterministic_drop_messages: Set[str] = set()
        self.deterministic_drop_acks: Set[str] = set()
        self.deterministic_faults: Dict[str, str] = {}

    @classmethod
    def get_instance(cls) -> "SimulatedTransport":
        if cls._instance is None:
            cls._instance = SimulatedTransport()
        return cls._instance

    def reset(self):
        """Resets all simulation parameters and fault injections to nominal online state."""
        self.is_online = True
        self.latency_ms = 0.0
        self.drop_message_prob = 0.0
        self.drop_ack_prob = 0.0
        self.arm_drop_next_message = False
        self.arm_drop_next_ack = False
        self.arm_corrupt_next_hmac = False
        self.active_preset = "NOMINAL"
        self.deterministic_drop_messages.clear()
        self.deterministic_drop_acks.clear()
        self.deterministic_faults.clear()

    def apply_preset(self, preset_name: str):
        name = preset_name.upper()
        if name in self.PRESETS:
            cfg = self.PRESETS[name]
            self.is_online = cfg["is_online"]
            self.latency_ms = cfg["latency_ms"]
            self.drop_message_prob = cfg["drop_message_prob"]
            self.drop_ack_prob = cfg["drop_ack_prob"]
            self.active_preset = name
        else:
            raise ValueError(f"Unknown preset: {preset_name}")

    def arm_drop_message(self):
        self.arm_drop_next_message = True

    def arm_drop_ack(self):
        self.arm_drop_next_ack = True

    def arm_corrupt_hmac(self):
        self.arm_corrupt_next_hmac = True

    def disarm_all(self):
        self.arm_drop_next_message = False
        self.arm_drop_next_ack = False
        self.arm_corrupt_next_hmac = False

    def set_online(self, online: bool):
        self.is_online = bool(online)

    def set_latency(self, latency_ms: float):
        self.latency_ms = max(0.0, float(latency_ms))

    def set_drop_rate(self, prob: float):
        self.drop_message_prob = max(0.0, min(1.0, float(prob)))

    def set_ack_drop_rate(self, prob: float):
        self.drop_ack_prob = max(0.0, min(1.0, float(prob)))

    def drop_message(self, message_id: str):
        self.deterministic_drop_messages.add(message_id)

    def drop_ack(self, message_id: str):
        self.deterministic_drop_acks.add(message_id)

    def inject_fault(self, message_id: str, error_code: str):
        self.deterministic_faults[message_id] = error_code

    def transmit_peer(self, message_dict: Dict[str, Any], peer_url: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Transmits message bundle to remote peer daemon endpoint over HTTP with impairment pipeline."""
        import requests

        msg_id = message_dict.get("message_id", "")

        # Stage 1: Forward Path Impairments
        if self.latency_ms > 0:
            time.sleep(self.latency_ms / 1000.0)

        if not self.is_online:
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "TRANSPORT_OFFLINE",
                "transport_state": "OFFLINE",
                "latency_ms": self.latency_ms,
            }

        if self.arm_drop_next_message:
            self.arm_drop_next_message = False
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "PACKET_DROPPED",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        if self.arm_corrupt_next_hmac:
            self.arm_corrupt_next_hmac = False
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "HMAC_VERIFICATION_FAILED",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        if msg_id in self.deterministic_faults:
            err = self.deterministic_faults.pop(msg_id)
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": err,
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        if msg_id in self.deterministic_drop_messages:
            self.deterministic_drop_messages.remove(msg_id)
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "PACKET_DROPPED",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        if self.drop_message_prob > 0 and random.random() < self.drop_message_prob:
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "PACKET_DROPPED",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        # Stage 2: HTTP Peer Transmission
        import base64
        url = peer_url.rstrip("/")
        if not url.endswith("/endpoints/incoming"):
            url = f"{url}/endpoints/incoming"

        tx_payload = dict(message_dict)
        if isinstance(tx_payload.get("payload"), (bytes, bytearray)):
            tx_payload["payload"] = base64.b64encode(tx_payload["payload"]).decode("ascii")

        try:
            resp = requests.post(url, json=tx_payload, timeout=timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.RequestException):
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "TRANSPORT_OFFLINE",
                "transport_state": "OFFLINE",
                "latency_ms": self.latency_ms,
            }

        if resp.status_code == 422:
            try:
                err_data = resp.json()
                err_code = err_data.get("error", "CRYPTO_AUTHENTICATION_FAILED")
                detail = err_data.get("detail", "Peer rejected corrupted/tampered ciphertext")
            except Exception:
                err_code = "CRYPTO_AUTHENTICATION_FAILED"
                detail = "Peer rejected corrupted/tampered ciphertext"
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": err_code,
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
                "detail": detail,
            }

        if resp.status_code not in (200, 201):
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": f"PEER_HTTP_{resp.status_code}",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        try:
            ack_data = resp.json()
        except Exception:
            ack_data = {}

        # Stage 3: Return Path Impairments (ACK Delivery)
        if self.arm_drop_next_ack:
            self.arm_drop_next_ack = False
            return {
                "delivered_to_receiver": True,
                "ack_delivered_to_sender": False,
                "error_code": "ACK_LOST",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
                "ack_response": ack_data,
            }

        if msg_id in self.deterministic_drop_acks:
            self.deterministic_drop_acks.remove(msg_id)
            return {
                "delivered_to_receiver": True,
                "ack_delivered_to_sender": False,
                "error_code": "ACK_LOST",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
                "ack_response": ack_data,
            }

        if self.drop_ack_prob > 0 and random.random() < self.drop_ack_prob:
            return {
                "delivered_to_receiver": True,
                "ack_delivered_to_sender": False,
                "error_code": "ACK_LOST",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
                "ack_response": ack_data,
            }

        return {
            "delivered_to_receiver": True,
            "ack_delivered_to_sender": True,
            "error_code": None,
            "transport_state": "ONLINE",
            "latency_ms": self.latency_ms,
            "ack_response": ack_data,
        }

    def transmit(self, message_dict: Dict[str, Any], peer_url: Optional[str] = None) -> Dict[str, Any]:
        """Simulates transmission of message from sender to recipient over link.
        
        If peer_url is provided, delegates to transmit_peer() over HTTP REST.
        Otherwise executes in-process simulation.
        
        Returns a result dict:
          {
            "delivered_to_receiver": bool,
            "ack_delivered_to_sender": bool,
            "error_code": str or None,
            "transport_state": "ONLINE" | "OFFLINE",
            "latency_ms": float,
          }
        """
        if peer_url:
            return self.transmit_peer(message_dict, peer_url)

        msg_id = message_dict.get("message_id", "")

        # 1. Apply artificial latency if configured
        if self.latency_ms > 0:
            time.sleep(self.latency_ms / 1000.0)

        # 2. Check if transport is offline
        if not self.is_online:
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "TRANSPORT_OFFLINE",
                "transport_state": "OFFLINE",
                "latency_ms": self.latency_ms,
            }

        # 3. Check single-shot message drop before statistical drops
        if self.arm_drop_next_message:
            self.arm_drop_next_message = False  # Auto-disarm immediately
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "PACKET_DROPPED",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        # Check single-shot HMAC corruption
        if self.arm_corrupt_next_hmac:
            self.arm_corrupt_next_hmac = False  # Auto-disarm immediately
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "HMAC_VERIFICATION_FAILED",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        # 4. Check deterministic fault injection
        if msg_id in self.deterministic_faults:
            err = self.deterministic_faults.pop(msg_id)
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": err,
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        # 5. Check message drop (deterministic or statistical)
        if msg_id in self.deterministic_drop_messages:
            self.deterministic_drop_messages.remove(msg_id)
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "PACKET_DROPPED",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        if self.drop_message_prob > 0 and random.random() < self.drop_message_prob:
            return {
                "delivered_to_receiver": False,
                "ack_delivered_to_sender": False,
                "error_code": "PACKET_DROPPED",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        # Message reached receiver!
        # Check single-shot ACK drop on return path
        if self.arm_drop_next_ack:
            self.arm_drop_next_ack = False  # Auto-disarm immediately
            return {
                "delivered_to_receiver": True,
                "ack_delivered_to_sender": False,
                "error_code": "ACK_LOST",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        # 6. Check ACK drop on return path
        if msg_id in self.deterministic_drop_acks:
            self.deterministic_drop_acks.remove(msg_id)
            return {
                "delivered_to_receiver": True,
                "ack_delivered_to_sender": False,
                "error_code": "ACK_LOST",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        if self.drop_ack_prob > 0 and random.random() < self.drop_ack_prob:
            return {
                "delivered_to_receiver": True,
                "ack_delivered_to_sender": False,
                "error_code": "ACK_LOST",
                "transport_state": "ONLINE",
                "latency_ms": self.latency_ms,
            }

        # Both forward and return paths succeeded!
        return {
            "delivered_to_receiver": True,
            "ack_delivered_to_sender": True,
            "error_code": None,
            "transport_state": "ONLINE",
            "latency_ms": self.latency_ms,
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_online": self.is_online,
            "latency_ms": self.latency_ms,
            "drop_message_prob": self.drop_message_prob,
            "drop_ack_prob": self.drop_ack_prob,
            "active_preset": self.active_preset,
            "armed_faults": {
                "drop_message": self.arm_drop_next_message,
                "drop_ack": self.arm_drop_next_ack,
                "corrupt_hmac": self.arm_corrupt_next_hmac,
            },
            "deterministic_drop_messages_count": len(self.deterministic_drop_messages),
            "deterministic_drop_acks_count": len(self.deterministic_drop_acks),
            "transport_mode": "SIMULATION",
        }


transport = SimulatedTransport.get_instance()
