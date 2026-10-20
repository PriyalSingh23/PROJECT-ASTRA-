"""Tactical RF Link Budget and Propagation Physics Engine.

Computes Free Space Path Loss (FSPL), Received Power (Prx), Signal-to-Noise Ratio (SNR),
and Link Margin across tactical VHF, UHF, ISM, and Airborne microwave bands.
"""
import math
from typing import Dict, Any, Optional

# Tactical Frequency & Power Presets
TACTICAL_BAND_PRESETS = {
    "VHF_TACTICAL": {
        "name": "VHF High-Power Tactical (144 MHz)",
        "freq_mhz": 144.0,
        "tx_power_dbm": 47.0,  # 50 W
        "tx_gain_dbi": 2.15,   # Dipole
        "rx_gain_dbi": 2.15,
        "rx_sensitivity_dbm": -118.0,
        "description": "Long-range tactical combat net radio with strong diffraction around terrain",
    },
    "UHF_MOTOTRBO": {
        "name": "UHF MOTOTRBO DMR (433 MHz)",
        "freq_mhz": 433.0,
        "tx_power_dbm": 37.0,  # 5 W
        "tx_gain_dbi": 2.15,
        "rx_gain_dbi": 2.15,
        "rx_sensitivity_dbm": -114.0,
        "description": "Standard commercial and tactical digital mobile radio standard",
    },
    "ISM_TACTICAL_MESH": {
        "name": "ISM 915 MHz Tactical Mesh",
        "freq_mhz": 915.0,
        "tx_power_dbm": 30.0,  # 1 W
        "tx_gain_dbi": 3.0,
        "rx_gain_dbi": 3.0,
        "rx_sensitivity_dbm": -110.0,
        "description": "High-throughput ad-hoc squad mesh and ground relay backbone",
    },
    "AIRBORNE_DOWNLINK": {
        "name": "L-Band UAV Downlink (1.4 GHz)",
        "freq_mhz": 1400.0,
        "tx_power_dbm": 33.0,  # 2 W
        "tx_gain_dbi": 5.5,    # Directional patch
        "rx_gain_dbi": 9.0,    # Ground station tracking antenna
        "rx_sensitivity_dbm": -108.0,
        "description": "Line-of-sight aerial relay corridor from high-altitude UAV platform",
    },
}


def calculate_link_budget(
    distance_km: float,
    freq_mhz: float = 433.0,
    tx_power_dbm: float = 37.0,
    tx_gain_dbi: float = 2.15,
    rx_gain_dbi: float = 2.15,
    cable_loss_db: float = 1.0,
    rx_sensitivity_dbm: float = -114.0,
    bandwidth_hz: float = 1_000_000.0,  # 1 MHz channel bandwidth
    noise_figure_db: float = 6.0,
) -> Dict[str, Any]:
    """Calculates comprehensive RF link budget using Friis transmission equation.
    
    FSPL(dB) = 20 * log10(d_km) + 20 * log10(f_mhz) + 32.44
    Prx(dBm) = Ptx + Gtx + Grx - FSPL - L_cable
    Noise Floor = -174 + 10*log10(BW) + NF
    SNR = Prx - Noise Floor
    Link Margin = Prx - Sensitivity
    """
    if distance_km <= 0.001:
        distance_km = 0.001  # Minimum 1 meter clamp

    # 1. Free Space Path Loss (FSPL) in dB
    fspl_db = 20.0 * math.log10(distance_km) + 20.0 * math.log10(freq_mhz) + 32.44

    # 2. Total Effective Isotropic Radiated Power (EIRP)
    eirp_dbm = tx_power_dbm + tx_gain_dbi - cable_loss_db

    # 3. Received Signal Strength (Prx) in dBm
    rx_power_dbm = eirp_dbm + rx_gain_dbi - fspl_db

    # 4. Thermal Noise Floor calculation
    thermal_noise_dbm = -174.0 + 10.0 * math.log10(bandwidth_hz) + noise_figure_db

    # 5. Signal to Noise Ratio (SNR)
    snr_db = rx_power_dbm - thermal_noise_dbm

    # 6. Link Margin (fading headroom before loss of lock)
    link_margin_db = rx_power_dbm - rx_sensitivity_dbm

    # 7. Operational Health Classification
    if link_margin_db >= 15.0:
        status = "OPTIMAL"
        status_color = "#10b981"  # Emerald green
        status_desc = "Robust link with substantial fading reserve (> 15 dB)"
    elif link_margin_db >= 6.0:
        status = "MARGINAL"
        status_color = "#f59e0b"  # Amber
        status_desc = "Acceptable link; susceptible to heavy multipath or weather fade (6–15 dB)"
    else:
        status = "FADE_THREAT"
        status_color = "#ef4444"  # Red
        status_desc = "Severe link degradation (< 6 dB margin); triggers ad-hoc mesh rerouting"

    return {
        "distance_km": round(distance_km, 3),
        "freq_mhz": round(freq_mhz, 2),
        "fspl_db": round(fspl_db, 2),
        "eirp_dbm": round(eirp_dbm, 2),
        "rx_power_dbm": round(rx_power_dbm, 2),
        "thermal_noise_dbm": round(thermal_noise_dbm, 2),
        "snr_db": round(snr_db, 2),
        "rx_sensitivity_dbm": round(rx_sensitivity_dbm, 2),
        "link_margin_db": round(link_margin_db, 2),
        "status": status,
        "status_color": status_color,
        "status_desc": status_desc,
    }
