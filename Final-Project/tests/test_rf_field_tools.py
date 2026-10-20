"""Unit and regression tests for Phase 9: RF Field Tools, PCAP Wireshark Export & Link Budget HUD."""
import struct
import pytest
from messaging.pcap import (
    TacticalPcapCaptureBuffer,
    PCAP_MAGIC_MICROSECONDS,
    PCAP_VERSION_MAJOR,
    PCAP_VERSION_MINOR,
    LINKTYPE_DLT_USER0,
)
from messaging.link_budget import calculate_link_budget, TACTICAL_BAND_PRESETS
from messaging.server import create_app


def test_pcap_binary_file_structure():
    """Verify standard libpcap 2.4 header format and record parsing."""
    buf = TacticalPcapCaptureBuffer(capacity=10)
    packet_1 = b"\x53\x48\x44\x57\x03\x00\x00\x01\xDE\xAD\xBE\xEF"
    packet_2 = b"\x53\x48\x44\x57\x03\x00\x00\x02\xCA\xFE\xBA\xBE"

    buf.record(packet_1, {"type": "TX"})
    buf.record(packet_2, {"type": "RX"})

    assert buf.count() == 2
    pcap_data = buf.generate_pcap()

    # Total size: 24 (file header) + 16 (pkt 1 hdr) + 12 (pkt 1) + 16 (pkt 2 hdr) + 12 (pkt 2) = 80 bytes
    assert len(pcap_data) == 80

    # Parse 24-byte libpcap file header
    magic, v_maj, v_min, thiszone, sigfigs, snaplen, linktype = struct.unpack("<IHHiIII", pcap_data[:24])
    assert magic == PCAP_MAGIC_MICROSECONDS
    assert v_maj == PCAP_VERSION_MAJOR
    assert v_min == PCAP_VERSION_MINOR
    assert snaplen == 65535
    assert linktype == LINKTYPE_DLT_USER0

    # Parse first packet header (at offset 24)
    ts_sec, ts_usec, caplen, orig_len = struct.unpack("<IIII", pcap_data[24:40])
    assert caplen == 12
    assert orig_len == 12
    assert pcap_data[40:52] == packet_1


def test_link_budget_friis_propagation():
    """Verify Friis Free Space Path Loss and link margin computations."""
    # Distance = 10 km, Freq = 433 MHz, Ptx = 37 dBm (5W), Gtx = 2.15, Grx = 2.15, Sens = -114 dBm
    res = calculate_link_budget(
        distance_km=10.0,
        freq_mhz=433.0,
        tx_power_dbm=37.0,
        tx_gain_dbi=2.15,
        rx_gain_dbi=2.15,
        cable_loss_db=1.0,
        rx_sensitivity_dbm=-114.0,
    )

    # Theoretical FSPL = 20*log10(10) + 20*log10(433) + 32.44 = 20 + 52.73 + 32.44 = 105.17 dB
    assert 104.5 <= res["fspl_db"] <= 106.0
    # Prx = 37 + 2.15 + 2.15 - 1.0 - 105.17 = -64.87 dBm
    assert -66.0 <= res["rx_power_dbm"] <= -63.5
    # Margin = Prx - (-114) = ~49 dB -> Optimal
    assert res["link_margin_db"] > 15.0
    assert res["status"] == "OPTIMAL"


def test_link_budget_fade_threat_at_extreme_range():
    """Verify link margin status drops to FADE_THREAT when beyond operational range."""
    # Distance = 200 km, Freq = 915 MHz, Ptx = 10 dBm (10mW), Sens = -100 dBm
    res = calculate_link_budget(
        distance_km=200.0,
        freq_mhz=915.0,
        tx_power_dbm=10.0,
        tx_gain_dbi=0.0,
        rx_gain_dbi=0.0,
        rx_sensitivity_dbm=-100.0,
    )
    assert res["status"] == "FADE_THREAT"
    assert res["link_margin_db"] < 6.0


def test_api_diagnostics_pcap_endpoint():
    """Verify HTTP GET /api/v1/diagnostics/pcap streams valid PCAP file."""
    app = create_app()
    client = app.test_client()

    resp = client.get("/api/v1/diagnostics/pcap")
    assert resp.status_code == 200
    assert resp.mimetype == "application/vnd.tcpdump.pcap"
    assert resp.headers.get("X-Pcap-LinkType") == "147"
    assert len(resp.data) >= 24

    # Verify magic
    magic = struct.unpack("<I", resp.data[:4])[0]
    assert magic == PCAP_MAGIC_MICROSECONDS


def test_api_rf_link_budget_endpoint():
    """Verify HTTP POST /api/v1/rf/link-budget calculates and returns presets."""
    app = create_app()
    client = app.test_client()

    payload = {
        "preset": "ISM_TACTICAL_MESH",
        "distance_km": 8.5,
    }
    resp = client.post("/api/v1/rf/link-budget", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["distance_km"] == 8.5
    assert data["freq_mhz"] == 915.0
    assert "link_margin_db" in data
    assert "status" in data
    assert "presets" in data
