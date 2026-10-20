import uuid
import struct
import hmac
import hashlib
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any

# Framing Constants
MESH_MAGIC = b"MSH"                     # 3 bytes
MESH_HEADER_FORMAT = "!3sBBBBH16s"       # exactly 25 bytes
MESH_HEADER_LEN = 25

# Priority & Custody Flags
FLAG_ROUTINE = 0x00      # Low priority routine traffic
FLAG_FLASH = 0x01        # Tactical Flash emergency traffic
FLAG_IMMEDIATE = 0x02    # High priority immediate traffic
FLAG_CUSTODY_REQ = 0x80  # Demands per-hop CUSTODY_ACK transfer handshake

# Deterministic Bitmask Index Mapping for Loop Prevention (MSH-02)
NODE_BIT_INDICES: Dict[str, int] = {
    "endpoint-a": 0,          # 0x0001
    "relay-ground-01": 1,     # 0x0002
    "relay-convoy-01": 2,     # 0x0004
    "relay-ground-02": 3,     # 0x0008
    "relay-uav-alpha": 4,     # 0x0010
    "relay-uav-bravo": 5,     # 0x0020
    "endpoint-b": 6,          # 0x0040
    "relay-aerial-sim-01": 7, # 0x0080
}

CUSTODY_SECRET_DEFAULT = b"SHADOWCOMM-CUSTODY-KEY-v1"


@dataclass
class MeshBundleHeader:
    """
    25-Byte Cleartext Outer Binary Mesh Bundle Header.
    Allows intermediary relays to inspect and update routing metadata
    without decrypting or corrupting post-quantum Envelope v3 ciphertexts.
    """
    magic: bytes = MESH_MAGIC
    flags: int = FLAG_ROUTINE
    initial_ttl: int = 8
    remaining_ttl: int = 8
    hop_count: int = 0
    visited_bitmask: int = 0
    bundle_uuid: bytes = b"\x00" * 16

    def pack(self) -> bytes:
        """Serializes the header into exactly 25 binary bytes."""
        return struct.pack(
            MESH_HEADER_FORMAT,
            self.magic,
            self.flags,
            self.initial_ttl,
            self.remaining_ttl,
            self.hop_count,
            self.visited_bitmask,
            self.bundle_uuid,
        )

    @classmethod
    def unpack(cls, data: bytes) -> Tuple["MeshBundleHeader", bytes]:
        """Parses header and returns (header, inner_payload)."""
        if len(data) < MESH_HEADER_LEN:
            raise ValueError(f"Data length {len(data)} is shorter than MESH_HEADER_LEN ({MESH_HEADER_LEN})")

        magic, flags, init_ttl, rem_ttl, hop_count, bitmask, uuid_bytes = struct.unpack(
            MESH_HEADER_FORMAT, data[:MESH_HEADER_LEN]
        )
        if magic != MESH_MAGIC:
            raise ValueError(f"Invalid mesh magic bytes: {magic!r}, expected {MESH_MAGIC!r}")

        header = cls(
            magic=magic,
            flags=flags,
            initial_ttl=init_ttl,
            remaining_ttl=rem_ttl,
            hop_count=hop_count,
            visited_bitmask=bitmask,
            bundle_uuid=uuid_bytes,
        )
        payload = data[MESH_HEADER_LEN:]
        return header, payload

    def has_visited(self, node_id: str) -> bool:
        """Checks if node_id has already processed this bundle."""
        bit_idx = NODE_BIT_INDICES.get(node_id)
        if bit_idx is None:
            return False
        return bool(self.visited_bitmask & (1 << bit_idx))

    def mark_visited(self, node_id: str):
        """Sets the visited bit for node_id."""
        bit_idx = NODE_BIT_INDICES.get(node_id)
        if bit_idx is not None:
            self.visited_bitmask |= (1 << bit_idx)

    def decrement_ttl(self) -> bool:
        """Decrements remaining TTL and increments hop count. Returns False if expired."""
        self.remaining_ttl -= 1
        self.hop_count += 1
        return self.remaining_ttl > 0


def generate_custody_ack_token(
    node_id: str,
    bundle_uuid: bytes,
    hop_count: int,
    secret_key: bytes = CUSTODY_SECRET_DEFAULT,
) -> bytes:
    """Generates a 16-byte HMAC-SHA256 custody acknowledgment token."""
    uuid_hex = bundle_uuid.hex() if isinstance(bundle_uuid, bytes) else str(bundle_uuid)
    msg = f"CUSTODY_ACK:{node_id}:{uuid_hex}:{hop_count}".encode("utf-8")
    full_digest = hmac.new(secret_key, msg, hashlib.sha256).digest()
    return full_digest[:16]


def verify_custody_ack_token(
    token: bytes,
    node_id: str,
    bundle_uuid: bytes,
    hop_count: int,
    secret_key: bytes = CUSTODY_SECRET_DEFAULT,
) -> bool:
    """Verifies that a 16-byte custody token is authentic."""
    if not token or len(token) != 16:
        return False
    expected = generate_custody_ack_token(node_id, bundle_uuid, hop_count, secret_key)
    return hmac.compare_digest(token, expected)


def wrap_mesh_bundle(
    payload_bytes: bytes,
    bundle_uuid: Optional[uuid.UUID] = None,
    initial_ttl: int = 8,
    priority_flag: int = FLAG_ROUTINE,
    source_node_id: str = "endpoint-a",
) -> bytes:
    """Wraps an encrypted Envelope payload in a 25-byte outer MeshBundleHeader."""
    b_uuid = bundle_uuid.bytes if bundle_uuid is not None else uuid.uuid4().bytes
    flags = (priority_flag & 0x03) | FLAG_CUSTODY_REQ

    header = MeshBundleHeader(
        magic=MESH_MAGIC,
        flags=flags,
        initial_ttl=initial_ttl,
        remaining_ttl=initial_ttl,
        hop_count=0,
        visited_bitmask=0,
        bundle_uuid=b_uuid,
    )
    header.mark_visited(source_node_id)
    return header.pack() + payload_bytes


def process_hop_bundle(bundle_bytes: bytes, current_node_id: str) -> Tuple[bytes, MeshBundleHeader, Optional[str]]:
    """
    Simulates receipt and transit forwarding check at a relay hop.
    Enforces loop detection and hop TTL decrements.
    Returns (repacked_bytes, header, error_code).
    """
    header, payload = MeshBundleHeader.unpack(bundle_bytes)

    # 1. Loop Prevention Check
    if header.has_visited(current_node_id):
        return b"", header, "ROUTING_LOOP_DETECTED"

    # 2. TTL Decrement Check
    ttl_valid = header.decrement_ttl()
    if not ttl_valid:
        return b"", header, "BUNDLE_TTL_EXPIRED"

    # 3. Mark current node as visited
    header.mark_visited(current_node_id)

    # 4. Re-pack bundle with modified header and original untouched payload
    repacked = header.pack() + payload
    return repacked, header, None
