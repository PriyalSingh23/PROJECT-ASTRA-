"""
Regression tests for the field channel, the in-loop adversary and the
hard-negative bank (lpi_v4/lpi_field, lpi_adversary, lpi_synthetic + their
lpi_train wiring).
=========================================================================================

CPU-only, no radio, no checkpoint, a few seconds.

    pytest tests/test_lpi_field.py -q

What each block guards:

* the field channel is *opt-in*: disabled it must be bit-identical to the
  bench ``apply_channel`` the v4 checkpoint was gated on;
* the field channel keeps apply_channel's SNR contract (the trainer's noise
  is the noise the converter sees);
* multipath puts its echo exactly where the delay profile says;
* the ADC clips to headroom and quantises to its bit grid;
* the VT-CNN2 adversary takes real steps, reports orientation-proof accuracy,
  and -- via DetectorBank -- pushes gradients back into the generator (the
  cat-and-mouse);
* DetectorBank refreshes each detector on its own cadence and freezes with
  the trainer's ``d_stop`` schedule;
* the synthetic hard negatives are band-limited, deterministic, unit-power
  and physically ordered (constant-envelope GFSK has lower PAPR than 16-QAM);
* ``load_hdf5`` reads *both* GOLD layouts -- (k, T, 2) and (k, 2, T) -- which
  is a regression test for a bug that silently disabled --radioml entirely.
"""
import os
import sys

import numpy as np
import pytest

torch = pytest.importorskip("torch")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.join(ROOT, "lpi_v4")
sys.path.insert(0, V4)

from lpi_core import (LPIConfig, LPIGenerator, LPIDecoder,          # noqa: E402
                      apply_channel, unit_power)
from lpi_field import (DEFAULT_FIELD, PRESETS, apply_field_channel,  # noqa: E402
                       apply_field_np, channel_and_sync_field,
                       describe_field, field_preset)
from lpi_adversary import (DetectorBank, VTCNN2, _balanced_acc,      # noqa: E402
                           adversary_train_step, warden_loss)
from lpi_synthetic import MODS, synth_frame, synthesize_bank         # noqa: E402


# --------------------------------------------------------------------- field ----
def test_disabled_field_is_bit_identical_to_the_bench_channel():
    """The v4 pipeline's contract: --field off changes nothing."""
    cfg = LPIConfig()
    x = unit_power(torch.randn(4, 2, cfg.frame_len))
    torch.manual_seed(11)
    a, _ = apply_channel(x, cfg, snr_db=8.0, impairments=True)
    torch.manual_seed(11)
    b, p = apply_field_channel(x, cfg, snr_db=8.0, impairments=True,
                               field={"enabled": False})
    assert torch.equal(a, b)
    assert "field" not in p                      # no extra draws, no extra keys
    # impairments=False short-circuits to apply_channel too, presets or not
    torch.manual_seed(12)
    c, _ = apply_channel(x, cfg, snr_db=8.0, impairments=False)
    torch.manual_seed(12)
    d, _ = apply_field_channel(x, cfg, snr_db=8.0, impairments=False,
                               field=field_preset("team"))
    assert torch.equal(c, d)


def test_field_presets_are_complete_and_sane():
    cfg = LPIConfig()
    for name in PRESETS:
        f = field_preset(name)
        assert set(DEFAULT_FIELD) <= set(f)      # presets only override, never drop
        assert len(f["path_delays"]) == len(f["path_db"])
        assert min(f["path_delays"]) >= 0
        assert max(f["path_delays"]) < cfg.frame_len
        assert f["path_db"][0] == 0.0 and all(v <= 0.0 for v in f["path_db"])
        assert f["k_db"] >= 0.0 and f["doppler_hz"] >= 0.0
        assert 4 <= f["adc_bits"] <= 16
        assert 0.0 <= f["clip_headroom_db"] <= 40.0
        line = describe_field(f)
        assert isinstance(line, str) and "doppler" in line
    with pytest.raises(KeyError):                # a typo must not become "static"
        field_preset("typo")


def test_field_channel_changes_the_waveform_and_reports_it():
    cfg = LPIConfig()
    x = unit_power(torch.randn(3, 2, cfg.frame_len))
    torch.manual_seed(5)
    bench, _ = apply_channel(x, cfg, snr_db=50.0, impairments=True)
    torch.manual_seed(5)
    fld, p = apply_field_channel(x, cfg, snr_db=50.0, impairments=True,
                                 field=field_preset("nlos"))
    assert p.get("field") is True and p.get("path_delays") == (0, 3, 8)
    assert not torch.allclose(bench, fld, atol=1e-3)
    assert torch.isfinite(fld).all()


def test_field_channel_honours_the_requested_snr():
    """apply_channel's noise contract survives the field path.

    Same seed on both runs means every impairment draw cancels and only the
    noise differs.  The tight check uses a flat single-tap channel: white
    signal through it stays white, so the fractional-timing interpolator
    attenuates signal and noise by the same factor and the output ratio must
    equal the requested SNR.  The full ``team`` preset then gets a wider
    tolerance on purpose: multipath tilts the PSD low, so the RX interpolator
    filters the *white* noise a little harder than the signal -- a real partial
    matched-filter gain, ~+0.7 dB, not a broken noise model.
    """
    cfg = LPIConfig()
    x = unit_power(torch.randn(6, 2, cfg.frame_len))
    flat = {**field_preset("static"), "path_delays": (0,), "path_db": (0.0,)}
    torch.manual_seed(31)
    clean, _ = apply_field_channel(x, cfg, snr_db=200.0, impairments=True, field=flat)
    torch.manual_seed(31)
    noisy, _ = apply_field_channel(x, cfg, snr_db=9.0, impairments=True, field=flat)
    p_noise = float((noisy - clean).pow(2).mean())
    measured = 10.0 * np.log10(float(clean.pow(2).mean()) / p_noise)
    assert abs(measured - 9.0) < 0.3, f"flat channel: {measured:.2f} dB for 9 dB"

    team = field_preset("team")
    torch.manual_seed(31)
    clean2, _ = apply_field_channel(x, cfg, snr_db=200.0, impairments=True, field=team)
    torch.manual_seed(31)
    noisy2, _ = apply_field_channel(x, cfg, snr_db=9.0, impairments=True, field=team)
    p_noise2 = float((noisy2 - clean2).pow(2).mean())
    measured2 = 10.0 * np.log10(float(clean2.pow(2).mean()) / p_noise2)
    assert -0.3 < measured2 - 9.0 < 1.5, f"team preset: {measured2:.2f} dB for 9 dB"


def test_adc_quantises_and_respects_headroom():
    cfg = LPIConfig()
    x = unit_power(torch.randn(8, 2, cfg.frame_len))
    f = {**field_preset("team"), "adc_bits": 8, "clip_headroom_db": 6.0}
    torch.manual_seed(9)
    y, _ = apply_field_channel(x, cfg, snr_db=6.0, impairments=True, field=f)
    full = 10 ** (6.0 / 20.0)                   # AGC: per-dim RMS 1 -> full scale
    step = full / 128.0
    assert float(y.abs().max()) <= full + 0.51 * step      # clipped to headroom
    assert torch.unique(y).numel() <= 2 * 128 + 1          # on the 8-bit grid
    assert torch.allclose(y, torch.round(y / step) * step,
                          atol=step * 1e-3, rtol=0)


def test_fractional_timing_actually_shifts_the_waveform():
    """tau=0 must be the identity; tau!=0 must move samples (ADC kept quiet so
    the only difference in the chain is the interpolation itself)."""
    cfg = LPIConfig()
    x = unit_power(torch.randn(3, 2, cfg.frame_len))
    base = {**field_preset("static"), "doppler_hz": 0.0, "sfo_ppm": 0.0,
            "adc_bits": 32, "clip_headroom_db": 120.0}
    torch.manual_seed(77)
    a, _ = apply_field_channel(x, cfg, snr_db=50.0, impairments=True,
                               field={**base, "timing_frac": 0.0})
    torch.manual_seed(77)
    b, _ = apply_field_channel(x, cfg, snr_db=50.0, impairments=True,
                               field={**base, "timing_frac": 0.5})
    assert not torch.allclose(a, b, atol=1e-4)


def test_multipath_puts_an_echo_where_the_delay_says():
    """An impulse through a 2-tap channel reappears at the tap's delay, at the
    tap's relative power -- and nowhere in a 1-tap control run."""
    cfg = LPIConfig()
    x = torch.zeros(1, 2, cfg.frame_len)
    x[0, 0, 0] = 1.0
    common = {"k_db": 20.0, "doppler_hz": 0.0, "timing_frac": 0.0, "sfo_ppm": 0.0,
              "adc_bits": 32, "clip_headroom_db": 120.0}
    torch.manual_seed(13)
    e, _ = apply_field_channel(x, cfg, snr_db=120.0, impairments=True,
                               field={**common, "path_delays": (0, 8),
                                      "path_db": (0.0, -6.0)})
    torch.manual_seed(13)
    c, _ = apply_field_channel(x, cfg, snr_db=120.0, impairments=True,
                               field={**common, "path_delays": (0,),
                                      "path_db": (0.0,)})
    echo_at = float(e[0, 0, 7:10].abs().max())
    peak = float(e[0, 0].abs().max())
    assert echo_at > 0.3 * peak                 # -6 dB tap == ~0.5x the direct path
    ctrl = float(c[0, 0, 7:10].abs().max())
    assert ctrl < 0.02 * float(c[0, 0].abs().max())   # a 1-tap channel has no echo


def test_channel_and_sync_field_runs_and_settles_to_unit_power():
    cfg = LPIConfig()
    x = unit_power(torch.randn(2, 2, cfg.frame_len))
    y, p = channel_and_sync_field(x, cfg, snr_db=5.0, impairments=True,
                                  field=field_preset("vehicle"))
    assert y.shape == x.shape and torch.isfinite(y).all()
    assert p.get("field") is True
    assert 0.5 < float(y.pow(2).mean()) < 2.0   # RX AGC normalises, like the bench
    y2, _ = channel_and_sync_field(x, cfg, snr_db=5.0, impairments=False,
                                   field=field_preset("vehicle"))
    assert 0.5 < float(y2.pow(2).mean()) < 2.0  # the unit_power fallback path too


def test_apply_field_np_is_deterministic_and_preserves_the_echo():
    """link_ber's numpy twin: same seed -> same channel, echo on the tap."""
    cfg = LPIConfig()
    rng = np.random.default_rng(0)
    fr = (rng.standard_normal(2048) + 1j * rng.standard_normal(2048)
          ).astype(np.complex128)
    f = field_preset("nlos")
    a = apply_field_np(fr, cfg, f, np.random.default_rng(7))
    b = apply_field_np(fr, cfg, f, np.random.default_rng(7))
    assert a.shape == fr.shape and np.isfinite(a).all()
    assert np.allclose(a, b)                    # seed-deterministic
    assert not np.allclose(a, fr)               # it actually did something
    f8 = {**f, "path_delays": (0, 8), "path_db": (0.0, -6.0), "k_db": 20.0,
          "doppler_hz": 0.0, "timing_frac": 0.0, "sfo_ppm": 0.0}
    imp = np.zeros(512, dtype=np.complex128)
    imp[0] = 1.0
    e = apply_field_np(imp, cfg, f8, np.random.default_rng(3))
    assert np.isfinite(e).all()
    # exactly two non-zero samples: the direct path and the tap's echo, nothing
    # else (timing_frac 0 -> the interpolation is the identity, no spill)
    nz = np.flatnonzero(np.abs(e) > 1e-12)
    assert nz.tolist() == [0, 8]
    assert abs(e[8]) > 0.1 * abs(e[0])       # the -6 dB tap is actually audible


# --------------------------------------------------------------- adversary ----
def test_vtcnn2_forward_and_backward():
    m = VTCNN2(seq_len=128)
    x = torch.randn(5, 2, 128, requires_grad=True)
    logits = m(x)
    assert logits.shape == (5, 2)               # row 1 == "signal"
    torch.nn.functional.cross_entropy(logits, torch.tensor([0, 1, 0, 1, 0])).backward()
    assert x.grad is not None and torch.isfinite(x.grad).all()
    assert any(p.grad is not None for p in m.parameters())
    m.eval()
    with torch.no_grad():
        assert m(torch.randn(2, 2, 128)).shape == (2, 2)


def test_adversary_step_updates_weights_and_accuracy_is_orientation_proof():
    m = VTCNN2(seq_len=64)
    before = [p.detach().clone() for p in m.parameters()]
    opt = torch.optim.Adam(m.parameters(), lr=1e-3)
    fake = torch.randn(8, 2, 64)
    real = torch.randn(8, 2, 64)
    loss = adversary_train_step(m, fake, real, opt)
    assert np.isfinite(loss)
    assert any(not torch.equal(a, b) for a, b in zip(before, list(m.parameters())))
    a1 = _balanced_acc(m, fake, real)
    a2 = _balanced_acc(m, real, fake)            # swapping the classes mirrors it
    assert 50.0 <= a1 <= 100.0                  # ...so the reported number can
    assert abs(a1 - a2) < 1e-3                   # never be the flattering one


def test_warden_loss_moved_without_changing_the_math():
    """warden_loss lives in lpi_adversary now -- one definition, same formula."""
    import lpi_train
    assert lpi_train.warden_loss is warden_loss
    w = torch.tensor([-3.0, -0.01, 0.0, 0.01, 0.5, 4.0])
    expected = (torch.sigmoid(w) - 0.5).abs().sub(0.02).clamp_min(0.0).pow(2).mean()
    assert torch.isclose(warden_loss(w), expected, atol=1e-7)
    inside = torch.tensor([0.0], requires_grad=True)   # inside the dead band
    warden_loss(inside).backward()
    assert float(inside.grad) == 0.0
    outside = torch.tensor([2.0], requires_grad=True)  # outside it
    warden_loss(outside).backward()
    assert float(outside.grad) > 0.0


def test_detector_bank_builds_steps_freezes_and_backprops():
    cfg = LPIConfig(frame_len=128)
    bank = DetectorBank(cfg, "cpu", views=("iq", "psd", "tf"), cnn=True,
                        cnn_refresh=3)
    assert bank.names == ["psd", "tf", "cnn"]   # iq is W1/W2's job: ignored here
    fake = torch.randn(4, 2, 128, requires_grad=True)
    real = torch.randn(4, 2, 128)
    d = bank.train_step(fake.detach(), real, trainable=True)
    assert set(d) == {"D_psd", "D_tf", "D_cnn"}
    assert all(np.isfinite(v) for v in d.values())
    assert bank.train_step(fake.detach(), real, trainable=False) == {}  # frozen regime
    terms = bank.gen_terms(fake)
    assert set(terms) == {"A_psd", "A_tf", "A_cnn"}
    sum(terms.values()).backward()              # generator-side gradient exists
    assert fake.grad is not None and torch.isfinite(fake.grad).all()
    accs = bank.accuracy(fake.detach(), real)
    assert set(accs) == {"psd", "tf", "cnn"}
    assert all(50.0 <= v <= 100.0 for v in accs.values())


def test_detector_bank_refresh_is_a_fresh_cat_on_its_own_cadence():
    cfg = LPIConfig(frame_len=128)
    bank = DetectorBank(cfg, "cpu", views=("psd",), cnn=True,
                        cnn_refresh=10, view_refresh=5)
    quiet = lambda *a, **k: None                                  # noqa: E731
    sd0 = bank.state_dict()
    bank.refresh_if_due(1, log=quiet)          # neither due at epoch 1
    sd1 = bank.state_dict()
    assert all(torch.equal(sd0[n][k], sd1[n][k]) for n in sd0 for k in sd0[n])
    bank.refresh_if_due(4, log=quiet)          # psd due (4 % 5 == 4), cnn not
    sd2 = bank.state_dict()
    assert any(not torch.equal(sd0["psd"][k], sd2["psd"][k]) for k in sd2["psd"])
    assert all(torch.equal(sd0["cnn"][k], sd2["cnn"][k]) for k in sd2["cnn"])
    bank.refresh_if_due(9, log=quiet)          # cnn due (9 % 10 == 9)
    sd3 = bank.state_dict()
    assert any(not torch.equal(sd2["cnn"][k], sd3["cnn"][k]) for k in sd3["cnn"])


def test_one_field_training_step_backprops_through_generator():
    """The whole new stack in one step: G -> field channel -> D, plus the
    in-loop detectors' generator terms, like lpi_train's loop does it."""
    from lpi_field import channel_and_sync_field, field_preset
    cfg = LPIConfig()
    G = LPIGenerator(cfg)
    D = LPIDecoder(cfg)
    D.tie_to(G)
    bank = DetectorBank(cfg, "cpu", views=("psd",), cnn=True, cnn_refresh=5)
    b = (torch.rand(4, cfg.n_bits) > 0.5).float() * 2 - 1
    z = torch.randn(4, cfg.z_dim)
    x = G(z, b)
    d = bank.train_step(x.detach(), torch.randn(4, 2, cfg.frame_len), trainable=True)
    assert set(d) == {"D_psd", "D_cnn"}
    y, p = channel_and_sync_field(x, cfg, snr_db=5.0, impairments=True,
                                  field=field_preset("team"))
    assert p.get("field") is True
    l_rec = torch.nn.functional.binary_cross_entropy_with_logits(
        D(y), (b > 0.5).float())
    loss = 20.0 * l_rec + sum(bank.gen_terms(x).values())
    loss.backward()
    g = [pp.grad for pp in G.parameters() if pp.grad is not None]
    assert g and all(torch.isfinite(t).all() for t in g)
    dd = [pp.grad for pp in D.parameters() if pp.grad is not None]
    assert dd and all(torch.isfinite(t).all() for t in dd)


# --------------------------------------------------------------- synthetic ----
def test_every_synthetic_modulation_runs_and_is_finite():
    rng = np.random.default_rng(0)
    for mod in MODS:
        f = synth_frame(mod, 256, snr_db=8.0, rng=rng)
        assert f.shape == (2, 256) and f.dtype == np.float32
        assert np.isfinite(f).all()


def test_synthetic_bank_is_deterministic_shaped_and_unit_power():
    a = synthesize_bank(18, 128, seed=4)
    b = synthesize_bank(18, 128, seed=4)
    assert a.shape == (18, 2, 128) and a.dtype == np.float32
    assert np.array_equal(a, b)                 # deterministic under --seed
    assert np.isfinite(a).all()
    p = (a.astype(np.float64) ** 2).reshape(18, 2, -1).sum(axis=1).mean(axis=1)
    assert np.all(p > 0.7) and np.all(p < 1.3)  # E[I^2 + Q^2] == 1 per frame
    c = synthesize_bank(18, 128, seed=5)
    assert not np.array_equal(a, c)


def test_hard_negatives_have_physical_papr_ordering():
    g = synth_frame("gfsk", 512, snr_db=60.0, rng=np.random.default_rng(0))
    q = synth_frame("16qam", 512, snr_db=60.0, rng=np.random.default_rng(1))

    def papr_db(f):
        s = f[0].astype(np.float64) + 1j * f[1].astype(np.float64)
        return 10.0 * np.log10(np.abs(s).max() ** 2 / np.mean(np.abs(s) ** 2))

    assert papr_db(g) < 0.5                     # constant envelope == 0 dB flat
    assert papr_db(g) < papr_db(q)              # RRC-shaped 16-QAM always peaks


# ------------------------------------------------------------------- HDF5 ----
def test_hdf5_loader_reads_both_gold_layouts(tmp_path):
    """Regression: load_hdf5 used to transpose the *wrong* axis, so every
    --radioml load silently failed and the trainer fell back to AWGN-only."""
    h5py = pytest.importorskip("h5py")
    from lpi_datasets import load_hdf5
    rs = np.random.RandomState(0)
    cases = [(48, 1024, 2),                 # GOLD layout: (k, T, 2)
             (48, 2, 512),                  # already (k, 2, T)
             (48, 2, 300)]                  # short capture -> must pad to target
    for i, shape in enumerate(cases):
        p = str(tmp_path / f"lay{i}.hdf5")
        with h5py.File(p, "w") as fh:
            fh.create_dataset("X", data=rs.rand(*shape).astype(np.float32))
        target = 512                        # short captures must pad up to target
        out = load_hdf5(p, n_take=16, target_len=target)
        assert out.shape == (16, 2, target), f"layout {shape} -> {out.shape}"
        assert np.isfinite(out).all()


def test_synthetic_bank_roundtrips_through_the_real_loader(tmp_path):
    """lpi_synthetic's HDF5 must be loadable by the trainer's own loader."""
    h5py = pytest.importorskip("h5py")
    from lpi_datasets import load_hdf5
    x = synthesize_bank(10, 256, seed=2)
    p = str(tmp_path / "hard.hdf5")
    with h5py.File(p, "w") as fh:
        fh.create_dataset("X", data=x)
    out = load_hdf5(p, n_take=10, target_len=256)
    assert out.shape == (10, 2, 256) and np.isfinite(out).all()


# ------------------------------------------------------------------ wiring ----
def test_device_flag_resolution():
    import lpi_train
    assert lpi_train._pick_device("cpu") == "cpu"
    assert lpi_train._pick_device("auto") in ("cuda", "mps", "cpu")
    if torch.backends.mps.is_available():
        assert lpi_train._pick_device("mps") == "mps"
    if torch.cuda.is_available():
        assert lpi_train._pick_device("cuda") == "cuda"
    else:
        with pytest.raises(SystemExit):
            lpi_train._pick_device("cuda")
