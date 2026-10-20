"""Tests for the Waveform Lab: LPI-CGAN vs. a conventional QPSK reference.

The scientific claim under test is a *comparison*, so every assertion here is
about the relationship between the two tracks being a real measurement of the
same battery under matched conditions — not about a hardcoded number.
"""
import pytest

from integration.waveform_lab.service import DOMAIN_META, WaveformLabService, waveform_lab_service
from messaging.server import create_app

DOMAIN_KEYS = [row[0] for row in DOMAIN_META]


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "waveform.db"))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="module")
def comparison():
    return WaveformLabService().compare(n_frames=4)


# ---------------------------------------------------------------------------
# Shape and comparability
# ---------------------------------------------------------------------------
def test_comparison_returns_both_tracks(comparison):
    assert set(comparison["tracks"].keys()) == {"lpi", "conventional"}
    for track in comparison["tracks"].values():
        assert track["available"] is True
        assert [d["key"] for d in track["domains"]] == DOMAIN_KEYS
        assert 0 <= track["n_pass"] <= len(DOMAIN_META)
        assert track["classification"] in (
            "INDISTINGUISHABLE_FROM_NOISE", "PARTIALLY_MASKED", "DETECTABLE", "UNAVAILABLE",
        )


def test_tracks_are_matched_on_payload_and_bandwidth(comparison):
    """Both tracks must carry the same bits in the same number of real samples."""
    frame = comparison["frame"]
    assert frame["n_bits"] == 128
    assert frame["out_len"] == 1024
    assert frame["out_len"] == 2 * frame["frame_len"]
    # The conventional spec must state the matched symbol rate.
    assert "sps=8" in comparison["tracks"]["conventional"]["spec"]
    lpi_shape = comparison["tracks"]["lpi"]["frame_shape"]
    conv_shape = comparison["tracks"]["conventional"]["frame_shape"]
    assert lpi_shape == conv_shape


def test_battery_is_the_same_size_for_each_track(comparison):
    for track in comparison["tracks"].values():
        assert track["n_domains"] == len(DOMAIN_META)
        assert len(track["domains"]) == len(DOMAIN_META)
        for dom in track["domains"]:
            assert dom["value"] is not None
            assert isinstance(dom["passed"], bool)
            assert dom["criterion"]


def test_views_are_populated_and_comparable(comparison):
    for track in comparison["tracks"].values():
        assert len(track["waveform"]) == 128
        assert len(track["constellation"]) == 512
        assert len(track["spectrum"]) == 512
    # The conventional track exposes symbol-rate points; LPI has no symbol grid.
    assert len(comparison["tracks"]["conventional"]["symbol_centers"]) > 0
    assert len(comparison["tracks"]["lpi"]["symbol_centers"]) == 0


# ---------------------------------------------------------------------------
# The claim
# ---------------------------------------------------------------------------
def test_lpi_outperforms_conventional_on_the_ew_battery(comparison):
    lpi = comparison["tracks"]["lpi"]
    conv = comparison["tracks"]["conventional"]
    if not lpi["available"]:  # pragma: no cover - checkpoint always present in CI
        pytest.skip(f"LPI checkpoint unavailable: {lpi.get('unavailable_reason')}")
    assert lpi["n_pass"] > conv["n_pass"], (
        f"LPI passed {lpi['n_pass']} vs conventional {conv['n_pass']}; "
        "the covert waveform must be harder to separate from noise."
    )


def test_conventional_waveform_is_detectable_by_ks(comparison):
    """A plain QPSK burst must fail the Gaussianity test — that is the point."""
    conv = {d["key"]: d for d in comparison["tracks"]["conventional"]["domains"]}
    assert conv["ks"]["passed"] is False
    assert conv["ks"]["value"] is not None and conv["ks"]["value"] < 0.05


def test_contrast_lists_which_domains_flip(comparison):
    contrast = comparison["contrast"]
    assert len(contrast) == len(DOMAIN_META)
    flipped = {c["key"] for c in contrast if c["flips"]}
    assert flipped, "at least one EW domain must flip between the two tracks"
    assert comparison["verdict"]["domains_flipped"] == len(flipped)


def test_comparison_is_cached():
    svc = WaveformLabService()
    first = svc.compare(n_frames=3)
    second = svc.compare(n_frames=3)
    assert first is second


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
def test_waveform_comparison_endpoint(client):
    res = client.get("/api/v1/research/waveform-comparison?frames=4")
    assert res.status_code == 200
    body = res.get_json()
    assert set(body["tracks"].keys()) == {"lpi", "conventional"}
    assert body["frame"]["n_bits"] == 128
    assert "comparison_basis" in body
    assert body["verdict"]["headline"]


def test_waveform_comparison_endpoint_survives_bad_frames(client):
    res = client.get("/api/v1/research/waveform-comparison?frames=not-a-number")
    assert res.status_code == 200
    assert len(res.get_json()["tracks"]) == 2


def test_singleton_is_shared_for_the_api():
    assert waveform_lab_service is not None
    assert isinstance(waveform_lab_service, WaveformLabService)
