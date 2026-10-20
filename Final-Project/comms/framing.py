"""Frame construction and parsing with CRC-32 integrity.

Layout (big-endian)::

    offset  size  field
    0       2     magic   = b"\\xA5\\x5A"
    2       1     version = 1
    3       1     type    (0 = data; reserved for voice/control later)
    4       2     seq     (uint16, wraps - receiver does not reorder)
    6       2     payload_len (uint16)
    8       N     payload
    8+N     4     CRC-32 (zlib) over bytes [0 .. 8+N)

``parse_frame`` is strict: total length must match ``payload_len``
exactly, magic/version must match, and the CRC must verify. Every
malformed input raises :class:`FrameError`; frames are never "best
effort" accepted, so an undetected-corruption claim can never hide
behind a lenient parser.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

MAGIC = b"\xA5\x5A"
VERSION = 1
TYPE_DATA = 0

_HEADER = struct.Struct(">2sBBHH")   # magic, version, type, seq, payload_len
_CRC = struct.Struct(">I")

FRAME_HEADER_SIZE = _HEADER.size     # 8
CRC_SIZE = _CRC.size                 # 4
MIN_FRAME_SIZE = FRAME_HEADER_SIZE + CRC_SIZE


class FrameError(ValueError):
    """Frame failed validation (bad magic/version/length/CRC)."""


@dataclass(frozen=True)
class ParsedFrame:
    payload: bytes
    seq: int
    ftype: int
    version: int


def build_frame(payload, seq: int, ftype: int = TYPE_DATA) -> bytes:
    """Serialize ``payload`` into a CRC-protected frame."""
    payload = bytes(payload)
    if len(payload) > 0xFFFF:
        raise FrameError(f"payload of {len(payload)} bytes exceeds uint16 length field")
    header = _HEADER.pack(MAGIC, VERSION, ftype & 0xFF, seq & 0xFFFF, len(payload))
    body = header + payload
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + _CRC.pack(crc)


def parse_frame(data) -> ParsedFrame:
    """Validate and unpack a frame; raise :class:`FrameError` on any defect."""
    data = bytes(data)
    if len(data) < MIN_FRAME_SIZE:
        raise FrameError(f"frame too short: {len(data)} bytes < {MIN_FRAME_SIZE}")
    magic, version, ftype, seq, payload_len = _HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise FrameError(f"bad magic {magic.hex()}")
    if version != VERSION:
        raise FrameError(f"unsupported version {version}")
    expected = FRAME_HEADER_SIZE + payload_len + CRC_SIZE
    if len(data) != expected:
        raise FrameError(f"length {len(data)} does not match payload_len "
                         f"(expected {expected})")
    body = data[:FRAME_HEADER_SIZE + payload_len]
    (stored_crc,) = _CRC.unpack(data[FRAME_HEADER_SIZE + payload_len:])
    if (zlib.crc32(body) & 0xFFFFFFFF) != stored_crc:
        raise FrameError("CRC-32 mismatch")
    payload = data[FRAME_HEADER_SIZE:FRAME_HEADER_SIZE + payload_len]
    return ParsedFrame(payload=payload, seq=seq, ftype=ftype, version=version)
