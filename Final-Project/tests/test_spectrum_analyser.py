import torch
import os
import pytest
import numpy as np
from messaging.server import create_app
from integration.workstation_service import workstation_service


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_spectrum.db")
    app = create_app(db_path=test_db)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_windowing_and_enbw_calculations():
    """Verify that FFT windowing calculations match exact scientific ENBW standards."""
    fs = 245760.0
    for fft_size in [256, 512, 1024]:
        bin_spacing = fs / fft_size

        # Test Blackman-Harris (ENBW ~ 2.004)
        analysis_bh = workstation_service.compute_signal_analysis(
            iq_samples=np.ones(fft_size, dtype=np.complex64),
            source_name="SYNTHESIS",
            is_calibrated_rf=False,
            fft_size=fft_size,
            window_type="blackman_harris"
        )
        rbw_bh = analysis_bh["statistics"]["rbw_hz"]
        enbw_bh = rbw_bh / bin_spacing
        assert abs(enbw_bh - 2.004) < 0.05
        assert analysis_bh["statistics"]["window"] == "Blackman-Harris"

        # Test Hann (ENBW ~ 1.500)
        analysis_hann = workstation_service.compute_signal_analysis(
            iq_samples=np.ones(fft_size, dtype=np.complex64),
            source_name="SYNTHESIS",
            is_calibrated_rf=False,
            fft_size=fft_size,
            window_type="hann"
        )
        rbw_hann = analysis_hann["statistics"]["rbw_hz"]
        enbw_hann = rbw_hann / bin_spacing
        assert abs(enbw_hann - 1.500) < 0.05
        assert analysis_hann["statistics"]["window"] == "Hann"

        # Test Hamming (ENBW ~ 1.363)
        analysis_hamm = workstation_service.compute_signal_analysis(
            iq_samples=np.ones(fft_size, dtype=np.complex64),
            source_name="SYNTHESIS",
            is_calibrated_rf=False,
            fft_size=fft_size,
            window_type="hamming"
        )
        rbw_hamm = analysis_hamm["statistics"]["rbw_hz"]
        enbw_hamm = rbw_hamm / bin_spacing
        assert abs(enbw_hamm - 1.363) < 0.05
        assert analysis_hamm["statistics"]["window"] == "Hamming"

        # Test Rectangular (ENBW ~ 1.000)
        analysis_rect = workstation_service.compute_signal_analysis(
            iq_samples=np.ones(fft_size, dtype=np.complex64),
            source_name="SYNTHESIS",
            is_calibrated_rf=False,
            fft_size=fft_size,
            window_type="rectangular"
        )
        rbw_rect = analysis_rect["statistics"]["rbw_hz"]
        enbw_rect = rbw_rect / bin_spacing
        assert abs(enbw_rect - 1.000) < 0.05
        assert analysis_rect["statistics"]["window"] == "Rectangular"


def test_psd_normalization_and_units():
    """Verify PSD points are correctly normalized in dBFS and frequencies span Nyquist band."""
    res = workstation_service.compute_signal_analysis(
        iq_samples=np.random.randn(256) + 1j * np.random.randn(256),
        source_name="SYNTHESIS",
        is_calibrated_rf=False,
        fft_size=256,
        window_type="blackman_harris"
    )

    spectrum = res["frequency_spectrum"]
    assert len(spectrum) == 256
    assert res["provenance"]["units"]["power"] == "dBFS"

    # Frequencies should span [-Fs/2, +Fs/2] (-122.88 kHz to +122.88 kHz)
    freqs = [pt["freq_khz"] for pt in spectrum]
    assert freqs[0] < -120.0
    assert freqs[-1] > 120.0

    # Max power in normalized dBFS should be <= 0.0 dBFS
    powers = [pt["power_db"] for pt in spectrum]
    assert max(powers) <= 0.05  # Within rounding
    assert min(powers) >= -120.0  # Dynamic range floor


def test_spectrogram_waterfall_structure():
    """Verify 2D spectrogram waterfall matrix structure and time slices."""
    res = workstation_service.compute_signal_analysis(
        iq_samples=np.random.randn(512) + 1j * np.random.randn(512),
        source_name="SYNTHESIS",
        is_calibrated_rf=False,
        fft_size=256
    )

    spectrogram = res["spectrogram"]
    assert len(spectrogram) > 0

    first_row = spectrogram[0]
    assert "time_step" in first_row
    assert "freq_bin" in first_row
    assert "intensity" in first_row


def test_autocorrelation_sequence():
    """Verify discrete autocorrelation sequence up to lag 31 and normalization at lag 0."""
    res = workstation_service.compute_signal_analysis(
        iq_samples=np.random.randn(256) + 1j * np.random.randn(256),
        source_name="SYNTHESIS",
        is_calibrated_rf=False
    )

    autocorr = res["autocorrelation"]
    assert len(autocorr) == 32  # Lags 0 to 31 inclusive
    assert autocorr[0]["lag"] == 0
    assert abs(autocorr[0]["correlation"] - 1.0) < 1e-4

    # For noise-like waveforms, autocorrelation at non-zero lags should decay rapidly
    for pt in autocorr[1:]:
        assert pt["correlation"] <= 1.0
        assert pt["correlation"] >= 0.0


def test_signal_statistics():
    """Verify statistical metrics (PAPR, kurtosis, entropy, KS test, circularity)."""
    res = workstation_service.compute_signal_analysis(
        iq_samples=np.random.randn(512) + 1j * np.random.randn(512),
        source_name="SYNTHESIS",
        is_calibrated_rf=False
    )

    stats = res["statistics"]
    assert "peak_amplitude" in stats
    assert "rms_amplitude" in stats
    assert "papr_db" in stats
    assert "spectral_kurtosis" in stats
    assert "spectral_entropy" in stats
    assert "ks_p_value" in stats
    assert "circularity" in stats

    assert stats["peak_amplitude"] >= stats["rms_amplitude"]
    assert stats["papr_db"] >= 0.0
    # Kurtosis for Gaussian-like noise is close to 3.0
    assert 2.0 <= stats["spectral_kurtosis"] <= 4.0
    # Spectral entropy should be high for spread spectrum
    assert stats["spectral_entropy"] > 0.8
    # IQ circularity should be low for proper complex Gaussian
    assert stats["circularity"] < 0.3


def test_signal_source_selection_and_fallback():
    """Verify behavior of SYNTHESIS, RECORDED_IQ, and LIVE_SDR with disconnected hardware."""
    # 1. Synthesis source
    syn_res = workstation_service.get_signal_intelligence_data(source="SYNTHESIS")
    assert syn_res["status"] == "ONLINE"
    assert syn_res["provenance"]["is_calibrated_rf"] is False
    assert "SYNTHESIS" in syn_res["provenance"]["source"]

    # 2. Recorded IQ source
    rec_res = workstation_service.get_signal_intelligence_data(source="RECORDED_IQ")
    assert rec_res["status"] == "ONLINE"
    assert rec_res["provenance"]["is_calibrated_rf"] is False
    assert "RECORDED_IQ" in rec_res["provenance"]["source"]

    # 3. Live SDR source when hardware is disconnected
    sdr = workstation_service.probe_sdr_hardware()
    if not sdr["device_connected"]:
        sdr_res = workstation_service.get_signal_intelligence_data(source="LIVE_SDR")
        assert sdr_res["status"] == "HARDWARE_DISCONNECTED"
        assert sdr_res["provenance"]["is_calibrated_rf"] is False
        assert "FALLBACK" in sdr_res["provenance"]["source"] or "DISCONNECTED" in sdr_res["status"]
        assert "fallback" in sdr_res["provenance"]["notes"].lower()


def test_signal_analysis_api_endpoint(client):
    """Verify GET /api/v1/workstation/signal/analysis API endpoint with various parameters."""
    res = client.get("/api/v1/workstation/signal/analysis?source=SYNTHESIS&fft_size=512&window=hann")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ONLINE"
    assert data["provenance"]["fft_size"] == 512
    assert data["provenance"]["window"] == "Hann"
    assert len(data["frequency_spectrum"]) == 512

    # Test invalid parameter fallbacks
    res_default = client.get("/api/v1/workstation/signal/analysis?fft_size=9999&window=invalid")
    assert res_default.status_code == 200
    data_def = res_default.get_json()
    assert data_def["provenance"]["fft_size"] in [256, 512, 1024]


def test_calibrated_rf_vs_uncalibrated_digital_units():
    """Verify distinction between uncalibrated digital samples (dBFS) and calibrated 50 Ohm RF (dBm)."""
    # 1. Uncalibrated digital sample testing
    iq_dig = (np.random.randn(256) + 1j * np.random.randn(256)).astype(np.complex64)
    res_dig = workstation_service.compute_signal_analysis(
        iq_samples=iq_dig,
        source_name="SYNTHESIS",
        is_calibrated_rf=False,
        fft_size=256,
        window_type="blackman_harris"
    )
    assert res_dig["provenance"]["is_calibrated_rf"] is False
    assert res_dig["provenance"]["units"]["power"] == "dBFS"
    assert res_dig["provenance"]["units"]["amplitude"] == "FS (Normalized)"
    assert res_dig["provenance"]["calibration_badge"] == "UNCALIBRATED DIGITAL SAMPLES (dBFS)"
    assert max(p["power_db"] for p in res_dig["frequency_spectrum"]) <= 0.05

    # 2. Calibrated RF hardware testing
    iq_rf = (0.1 * (np.random.randn(256) + 1j * np.random.randn(256))).astype(np.complex64)
    res_rf = workstation_service.compute_signal_analysis(
        iq_samples=iq_rf,
        source_name="LIVE_SDR",
        is_calibrated_rf=True,
        fft_size=256,
        window_type="blackman_harris"
    )
    assert res_rf["provenance"]["is_calibrated_rf"] is True
    assert res_rf["provenance"]["units"]["power"] == "dBm"
    assert res_rf["provenance"]["units"]["amplitude"] == "V"
    assert res_rf["provenance"]["calibration_badge"] == "CALIBRATED RF HARDWARE (dBm)"
    # Calibrated power into 50 Ohm load should be a realistic RF power value in dBm
    rf_powers = [p["power_db"] for p in res_rf["frequency_spectrum"]]
    assert all(isinstance(p, float) for p in rf_powers)
    assert max(rf_powers) > -120.0


def test_data_updates_and_parameter_sweep():
    """Verify dynamic spectral updates across parameter sweeps (FFT size, windows, carrier tones)."""
    fs = 245760.0
    for n_fft in [256, 512, 1024]:
        for win in ["blackman_harris", "hann", "hamming", "rectangular"]:
            res = workstation_service.compute_signal_analysis(
                iq_samples=np.random.randn(n_fft) + 1j * np.random.randn(n_fft),
                source_name="SYNTHESIS",
                is_calibrated_rf=False,
                sample_rate_sps=fs,
                fft_size=n_fft,
                window_type=win
            )
            assert len(res["frequency_spectrum"]) == n_fft
            assert res["statistics"]["fft_size"] == n_fft
            assert len(res["spectrogram"]) > 0
            assert len(res["autocorrelation"]) == 32

    # Test dynamic response to a pure baseband sinusoid (tone at 20 kHz)
    t = np.arange(512) / fs
    f_tone = 20000.0
    tone_iq = np.exp(1j * 2 * np.pi * f_tone * t).astype(np.complex64)

    tone_res = workstation_service.compute_signal_analysis(
        iq_samples=tone_iq,
        source_name="SYNTHESIS",
        is_calibrated_rf=False,
        sample_rate_sps=fs,
        fft_size=256,
        window_type="blackman_harris"
    )
    # The peak frequency should be close to 20 kHz
    peak_pt = max(tone_res["frequency_spectrum"], key=lambda p: p["power_db"])
    assert abs(peak_pt["freq_khz"] - 20.0) < 5.0
    # PAPR for pure sinusoid is approx 0.0 dB (constant envelope |e^{jwt}|=1)
    assert tone_res["statistics"]["papr_db"] < 0.5


def test_disconnected_hardware_fallback_integrity():
    """Verify that when USRP hardware is absent, LIVE_SDR fails gracefully to recorded data fallback."""
    orig_probe = workstation_service.probe_sdr_hardware
    workstation_service.probe_sdr_hardware = lambda: {
        "driver_installed": True,
        "driver_version": "UHD_4.7.0.0",
        "device_connected": False,
        "device_count": 0,
        "devices": [],
        "operating_mode": "DISCONNECTED",
        "center_freq_hz": 2484000000.0,
        "sample_rate_sps": 245760.0,
        "decimation_ratio": 407,
        "master_clock_hz": 100000000.0,
        "tx_gain_db": 0.0,
        "rx_gain_db": 0.0
    }
    try:
        data = workstation_service.get_signal_intelligence_data(source="LIVE_SDR", fft_size=256)
        assert data["status"] == "HARDWARE_DISCONNECTED"
        assert data["provenance"]["is_calibrated_rf"] is False
        assert "HARDWARE DISCONNECTED" in data["provenance"]["source_label"] or "FALLBACK" in data["provenance"]["source_label"]
        assert "USRP" in data["warning"]
        assert len(data["time_domain"]) > 0
        assert len(data["frequency_spectrum"]) == 256
        assert len(data["constellation"]) > 0
        assert len(data["autocorrelation"]) == 32
        assert len(data["spectrogram"]) > 0
        assert "peak_amplitude" in data["statistics"]
    finally:
        workstation_service.probe_sdr_hardware = orig_probe


def test_recorded_iq_file_loading_npy_and_raw(tmp_path):
    """Verify parsing and loading of both .npy arrays and raw .fc32 binary baseband captures."""
    # 1. Test .npy complex64 load
    test_samples = (np.random.randn(128) + 1j * np.random.randn(128)).astype(np.complex64)
    npy_file = str(tmp_path / "test_iq.npy")
    np.save(npy_file, test_samples)

    loaded_npy, meta_npy = workstation_service.load_recorded_iq(file_path=npy_file)
    assert loaded_npy is not None
    assert len(loaded_npy) == 128
    assert meta_npy["format"] == "NPY_COMPLEX64"
    assert meta_npy["filename"] == "test_iq.npy"

    # 2. Test raw binary complex64 (.fc32) load
    fc32_file = str(tmp_path / "test_iq.fc32")
    test_samples.tofile(fc32_file)

    loaded_fc32, meta_fc32 = workstation_service.load_recorded_iq(file_path=fc32_file)
    assert loaded_fc32 is not None
    assert len(loaded_fc32) == 128
    assert meta_fc32["format"] in ["RAW_COMPLEX64_FC32", "NPY_COMPLEX64"]
    assert meta_fc32["filename"] == "test_iq.fc32"

    # 3. Test non-existent file
    missing_file = str(tmp_path / "does_not_exist.npy")
    loaded_miss, meta_miss = workstation_service.load_recorded_iq(file_path=missing_file)
    assert loaded_miss is None
    assert meta_miss["error"] == "FILE_NOT_FOUND"

