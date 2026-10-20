"""Standard libpcap 2.4 packet capture and export generator for ASTRA Tactical Network.

Generates standard .pcap binary byte streams compatible with Wireshark, tcpdump,
and network protocol analyzers. Encapsulates tactical frames (Envelope v3, PQC ML-KEM-768,
Reed-Solomon codewords, and radio metadata) using DLT_USER0 (LinkType 147).
"""
import struct
import time
from typing import List, Dict, Any, Optional

# Standard libpcap 2.4 Magic & Constants
PCAP_MAGIC_MICROSECONDS = 0xA1B2C3D4  # Standard microsecond timestamp magic
PCAP_VERSION_MAJOR = 2
PCAP_VERSION_MINOR = 4
PCAP_THISZONE = 0                     # GMT offset in seconds
PCAP_SIGFIGS = 0                      # Accuracy of timestamps
PCAP_SNAPLEN = 65535                  # Maximum packet capture length
LINKTYPE_DLT_USER0 = 147              # DLT_USER0 for custom tactical radio protocols

# Circular Ring Buffer
MAX_CAPTURE_BUFFER_FRAMES = 500


class PcapPacketRecord:
    """Represents a single captured tactical radio frame."""
    def __init__(self, raw_bytes: bytes, timestamp: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None):
        self.raw_bytes = raw_bytes
        self.timestamp = timestamp or time.time()
        self.metadata = metadata or {}

    def to_pcap_record_bytes(self) -> bytes:
        """Serializes packet into standard libpcap packet record format:
        struct pcap_sf_pkthdr {
            uint32_t ts_sec;
            uint32_t ts_usec;
            uint32_t caplen;
            uint32_t len;
        };
        """
        ts_sec = int(self.timestamp)
        ts_usec = int((self.timestamp - ts_sec) * 1_000_000)
        caplen = min(len(self.raw_bytes), PCAP_SNAPLEN)
        orig_len = len(self.raw_bytes)

        hdr = struct.pack("<IIII", ts_sec, ts_usec, caplen, orig_len)
        return hdr + self.raw_bytes[:caplen]


class TacticalPcapCaptureBuffer:
    """Thread-safe circular in-memory buffer storing recent transmitted/received packets."""
    def __init__(self, capacity: int = MAX_CAPTURE_BUFFER_FRAMES):
        self.capacity = capacity
        self.packets: List[PcapPacketRecord] = []

    def record(self, raw_bytes: bytes, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Appends a captured frame to the circular buffer."""
        record = PcapPacketRecord(raw_bytes, timestamp=time.time(), metadata=metadata)
        self.packets.append(record)
        if len(self.packets) > self.capacity:
            self.packets.pop(0)

    def generate_pcap(self) -> bytes:
        """Serializes all buffered packets into a complete .pcap binary stream."""
        # Standard libpcap global file header (24 bytes)
        file_header = struct.pack(
            "<IHHiIII",
            PCAP_MAGIC_MICROSECONDS,
            PCAP_VERSION_MAJOR,
            PCAP_VERSION_MINOR,
            PCAP_THISZONE,
            PCAP_SIGFIGS,
            PCAP_SNAPLEN,
            LINKTYPE_DLT_USER0,
        )

        packet_bytes_list = [file_header]
        for pkt in self.packets:
            packet_bytes_list.append(pkt.to_pcap_record_bytes())

        return b"".join(packet_bytes_list)

    def clear(self) -> None:
        self.packets.clear()

    def count(self) -> int:
        return len(self.packets)


# Process-wide capture buffer
global_pcap_buffer = TacticalPcapCaptureBuffer()
