#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lpi_train.py -- LPI-CGAN v4 trainer (Colab / local / CI, CPU / CUDA / MPS).
=======================================================================

    python lpi_train.py --epochs 120 --batch 64 --steps 60 --out lpi_v4.pt
    python lpi_train.py --radioml --data GOLD_XYZ_OSC.0001_1024.hdf5   # stronger warden
    python lpi_train.py --field --cnn-adversary --synth-real 20000 --init run/lpi_v4.best.pt --out run/field/lpi_v5.pt --export-dir run/field
    python lpi_train.py --field --field-preset vehicle

Loss (the paper's nine-component composite, plus the v4 reconstruction term):

    L_G = w_adv*L_D1 + 0.5*w_adv*L_D2 + 0.5*L_mean + 0.5*L_var + 3.0*L_pwr
        + 3.0*L_spec + 2.5*L_cyclo + 6.0*L_pnorm + 3.0*L_div + W_REC*L_rec

* L_D1/L_D2 : fool two wardens; D2's weights are re-initialised every 25 epochs
              (the paper's "periodic adversary refreshment").
* detectors : --cnn-adversary puts the RadioML VT-CNN2 -- the hostile EW
              receiver, previously a post-hoc evaluation *after* training --
              inside the loop (lpi_adversary.DetectorBank).  It is stepped every
              minibatch and re-drawn every --cnn-refresh epochs, so the generator
              faces a moving target instead of a fixed one: the cat-and-mouse.
* L_rec     : BCE on the *despread* bits through the full RF channel + pilot-aided
              front end, so the transmitter is designed against the receiver it
              will actually be paired with.  This term is the v4 addition: without
              it the generator has no incentive to stay invertible.
* the rest  : the eight EW domains, imported from lpi_stats so the loss and the
              published metric are literally the same code.

--field trains through the field-realistic channel (lpi_field: multipath with
Doppler, fractional-sample timing, SFO, ADC clipping) instead of the bench
channel.  --synth-real adds band-limited modulated hard negatives (RadioML 2018
is email-gated; lpi_synthetic is not) so the warden cannot pass by answering
"is this noise?" when the real question is "is this a signal?".

Everything is logged to CSV + (optionally) TensorBoard/W&B, and the best snapshot
is the one that passes all four gate metrics -- never "last epoch".
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys
import time
from typing import Dict

# MPS on torch 2.2 does not implement linalg.solve (the ZF detector in
# LPIDecoder) or fft.rfft (the spectral losses and the psd/tf warden views):
# without this, every --device mps run dies with NotImplementedError on the
# first decoder step.  Inert on cpu/cuda.  Must precede `import torch`.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lpi_core import (LPIConfig, LPIGenerator, LPIDecoder, Warden, channel_and_sync,
                      save_config, make_preamble, frame_with_pilot, sync_and_correct)
from lpi_adversary import DetectorBank, warden_loss            # noqa: E402  (moved here)
from lpi_stats import (loss_mean, loss_var, loss_kurtosis, loss_spectral_flatness,
                       loss_cyclo, loss_power, loss_diversity, loss_ks, ew_report,
                       composite_stat_loss)

GATE = {"ks": 0.05, "adv": 56.0, "ber": 0.01}          # pass thresholds (v4 = paper)


# =========================================================================
def set_seed(s: int) -> None:
    random.seed(s); np.random.seed(s); torch.manual_seed(s)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(s)


def _pick_device(want: str) -> str:
    """Resolve --device.  ``auto`` prefers cuda, then mps, then cpu.

    Why mps is offered at all: this repo's training box is an M1, and the old
    ``cuda if available else cpu`` line left its GPU doing nothing.  The ops the
    model needs that MPS lacks (linalg.solve, fft.rfft) fall back to CPU via
    PYTORCH_ENABLE_MPS_FALLBACK, which lpi_train sets before torch is imported.
    An explicit ``--device cpu`` is always available if the fallback costs more
    than it saves.
    """
    if want != "auto":
        if want == "cuda" and not torch.cuda.is_available():
            raise SystemExit("--device cuda requested but CUDA is not available")
        return want
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


# warden_loss() now lives in lpi_adversary.py (one definition for the trainer and
# the in-loop detectors) and is imported above; the name is unchanged.


def d_train_step(w: Warden, fake: torch.Tensor, real: torch.Tensor,
                 opt: torch.optim.Optimizer) -> float:
    opt.zero_grad()
    logits = torch.cat([w(fake).flatten(), w(real).flatten()])
    # labels must live on the same device as logits (MPS/CUDA); a CPU-side
    # label tensor raises "Expected all tensors to be on the same device".
    labels = torch.cat([torch.zeros(fake.shape[0], device=logits.device),
                        torch.ones(real.shape[0], device=logits.device)], 0)
    loss = F.binary_cross_entropy_with_logits(logits, labels)
    loss.backward()
    opt.step()
    return float(loss.detach())


# =========================================================================
# real-world "hard negatives" for the warden (GOLD / RadioML), if available
# =========================================================================
class RealBank:
    def __init__(self, path: str | None, n: int, target_len: int, enabled: bool):
        self.x = None
        if not enabled:
            return
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from lpi_datasets import find_and_load_real
            self.x = find_and_load_real(n, target_len, explicit=path)
        except Exception as e:                                  # noqa: BLE001
            print(f"[data] real-world reference unavailable ({e}); AWGN only")
        if self.x is not None:
            print(f"[data] real reference bank: {self.x.shape}")

    def sample(self, n: int, T: int, device) -> torch.Tensor | None:
        if self.x is None:
            return None
        i = np.random.randint(0, len(self.x), n)
        a = self.x[i]
        if a.shape[-1] != T:
            if a.shape[-1] > T:
                s = np.random.randint(0, a.shape[-1] - T)
                a = a[..., s:s + T]
            else:
                a = np.pad(a, ((0, 0), (0, 0), (0, T - a.shape[-1])))
        return torch.from_numpy(np.ascontiguousarray(a)).to(device)


# =========================================================================
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--steps", type=int, default=40, help="optimizer steps per epoch")
    ap.add_argument("--out", default="lpi_v4.pt")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    # architecture / waveform
    ap.add_argument("--n-bits", type=int, default=128)
    ap.add_argument("--frame-len", type=int, default=512)
    ap.add_argument("--pilot-len", type=int, default=64)
    ap.add_argument("--eps", type=float, default=0.10, help="masking blend factor")
    ap.add_argument("--ch", type=int, default=32)
    # channel
    ap.add_argument("--snr-lo", type=float, default=-2.0)
    ap.add_argument("--snr-hi", type=float, default=12.0)
    ap.add_argument("--fs", type=float, default=245760.0)
    ap.add_argument("--no-impair", action="store_true")
    # losses
    ap.add_argument("--w-rec", type=float, default=20.0)
    ap.add_argument("--w-adv", type=float, default=1.0)
    ap.add_argument("--w-stat", type=float, default=1.0)
    ap.add_argument("--w-cov", type=float, default=2.0,
                    help="weight of the Gram-spectrum (MP detector) matching term")
    ap.add_argument("--warmup", type=int, default=5,
                    help="epochs of reconstruction-only training before the "
                         "invisibility terms are annealed in")
    # data / logging
    ap.add_argument("--radioml", action="store_true")
    ap.add_argument("--data", default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--tb", default="runs/lpi_v4")
    ap.add_argument("--wandb", default="", help='e.g. "lpi-v4" to enable')
    ap.add_argument("--export-every", type=int, default=0)
    ap.add_argument("--export-dir", default="",
                    help="where generator_lpi.pt / decoder_lpi.pt / lpi_config.json are "
                         "written (default: next to --out). Smoke tests should point this "
                         "at a scratch folder -- export_for_grc() is called on every best "
                         "epoch, so a 6-epoch run aimed at run/ci.pt would otherwise leave "
                         "6-epoch TorchScript in run/, and the radio reads THAT folder.")
    ap.add_argument("--init", default="", help="warm-start G/D from this checkpoint")
    ap.add_argument("--d-stop-frac", type=float, default=0.6,
                    help="fraction of the run after which the wardens are FROZEN "
                         "(the paper's protocol: train the detector, then measure it)")
    ap.add_argument("--gate-every", type=int, default=2)
    # device / field realism / hostile receivers (the cat-and-mouse extras)
    ap.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda", "mps"),
                    help="auto = cuda > mps > cpu (an M1's GPU is otherwise idle)")
    ap.add_argument("--field", action="store_true",
                    help="train through the field-realistic channel (lpi_field): "
                         "multipath + Doppler + fractional timing + SFO + ADC")
    ap.add_argument("--field-preset", default="team",
                    choices=("static", "team", "vehicle", "nlos"),
                    help="which field scenario the --field channel models")
    ap.add_argument("--cnn-adversary", action="store_true",
                    help="co-train the RadioML VT-CNN2 hostile EW receiver in the "
                         "loop (re-drawn every --cnn-refresh epochs)")
    ap.add_argument("--cnn-refresh", type=int, default=10,
                    help="epochs between re-initialising the CNN adversary")
    ap.add_argument("--views", default="",
                    help="extra warden views as a comma list (iq, psd, tf); iq is "
                         "already covered by W1/W2 and is ignored here")
    ap.add_argument("--w-cnn", type=float, default=1.0,
                    help="weight of the CNN adversary term in L_G")
    ap.add_argument("--synth-real", type=int, default=0,
                    help="N synthetic band-limited modulated frames (lpi_synthetic) "
                         "added to the warden's real bank")
    args = ap.parse_args()

    set_seed(args.seed)
    device = _pick_device(args.device)
    torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
    cfg = LPIConfig(n_bits=args.n_bits, frame_len=args.frame_len,
                    pilot_len=args.pilot_len, dither_eps=args.eps, ch=args.ch,
                    fs=args.fs, snr_range=(args.snr_lo, args.snr_hi))
    print(f"[cfg] {json.dumps(cfg.to_dict(), indent=None)}")
    print(f"[cfg] spreading gain {cfg.gain_db:.2f} dB | frame {cfg.total_len} "
          f"samples = {cfg.total_len/cfg.fs*1e3:.2f} ms | "
          f"{cfg.n_bits/(cfg.total_len/cfg.fs):.0f} bit/s | device {device}")

    G = LPIGenerator(cfg).to(device)
    D = LPIDecoder(cfg).to(device)
    D.tie_to(G)
    warden_kwargs = dict(n_fft=cfg.frame_len, input="iq", ch=cfg.ch)
    W1 = Warden(**warden_kwargs).to(device)
    W2 = Warden(**warden_kwargs).to(device)
    # kept for the periodic D2 refresh below; the refreshed instance must be
    # re-stamped too (a bare Warden(**...) replacement lost _init_kwargs and
    # crashed the second refresh at epoch 49 of the first field run)
    W2._init_kwargs = warden_kwargs
    W1._init_kwargs = warden_kwargs
    optG = torch.optim.Adam(G.parameters(), lr=2e-4, betas=(0.5, 0.999))
    optD = torch.optim.Adam(D.parameters(), lr=2e-4, betas=(0.5, 0.999))
    optW = torch.optim.Adam(list(W1.parameters()) + list(W2.parameters()),
                            lr=1e-4, betas=(0.5, 0.999))

    field = None
    if args.field:
        from lpi_field import describe_field, field_preset
        field = field_preset(args.field_preset)
        print(f"[channel] field preset '{args.field_preset}': {describe_field(field)}")

    def chan(x_, snr_db=None):
        """One call site for "TX -> RX front end", bench or field."""
        if field is None:
            return channel_and_sync(x_, cfg, snr_db, impairments=not args.no_impair)
        from lpi_field import channel_and_sync_field
        return channel_and_sync_field(x_, cfg, snr_db,
                                      impairments=not args.no_impair, field=field)

    views = tuple(v.strip() for v in args.views.split(",") if v.strip())
    extra = (DetectorBank(cfg, device, views=views, cnn=args.cnn_adversary,
                          cnn_refresh=args.cnn_refresh, w_cnn=args.w_cnn)
             if (args.cnn_adversary or views) else None)
    if extra is not None and len(extra):
        print(f"[adversary] co-trained detectors: {', '.join(extra.names)} "
              f"(cnn refreshed every {args.cnn_refresh} epochs)")

    if args.init and os.path.exists(args.init):
        ck = torch.load(args.init, map_location=device, weights_only=False)
        G.load_state_dict(ck["generator"], strict=False)
        D.load_state_dict(ck["decoder"], strict=False)
        D.tie_to(G)
        if "warden1" in ck:
            W1.load_state_dict(ck["warden1"]); W2.load_state_dict(ck["warden2"])
            print(f"[init] warm start from {args.init} (epoch {ck.get('epoch')}) incl. wardens")
        else:
            print(f"[init] warm start from {args.init} (epoch {ck.get('epoch')})")
        if extra is not None:
            extra.load_state_dict(ck.get("detectors"))

    start = 1
    resume_best = None
    if args.resume and os.path.exists(args.out):
        ck = torch.load(args.out, map_location=device, weights_only=False)
        G.load_state_dict(ck["generator"]); D.load_state_dict(ck["decoder"])
        D.tie_to(G)
        start = int(ck.get("epoch", 0)) + 1
        if extra is not None:
            extra.load_state_dict(ck.get("detectors"))
        # the checkpoint stores them, so a resumed run continues them: warden
        # weights feed G's adversarial term every step, and Adam moments keep
        # the optimizers' steps continuous across the interruption
        if ck.get("warden1") is not None:
            W1.load_state_dict(ck["warden1"]); W2.load_state_dict(ck["warden2"])
        if ck.get("optG") is not None:
            optG.load_state_dict(ck["optG"]); optD.load_state_dict(ck["optD"])
        if ck.get("best") is not None:
            resume_best = float(ck["best"])
        print(f"[resume] {args.out} at epoch {ck.get('epoch')}"
              + (f", best score {resume_best:.1f}" if resume_best is not None else ""))

    bank = RealBank(args.data, 20000, cfg.frame_len, args.radioml)
    if args.synth_real > 0:
        # Hard negatives: the warden must learn "signal vs noise", not "noise vs
        # noise".  RadioML is email-gated; this is not, and it is shaped like a
        # radio's DAC output rather than an unfiltered symbol stream.
        from lpi_synthetic import synthesize_bank
        synth = synthesize_bank(args.synth_real, cfg.frame_len, seed=args.seed)
        bank.x = synth if bank.x is None else np.concatenate([bank.x, synth], 0)
        print(f"[data] synthetic hard negatives merged: {bank.x.shape}")

    log = args.log or (args.out + ".csv")
    new_log = not os.path.exists(log)
    cols = (["epoch", "sec", "loss_G", "bce", "D1", "D2", "adv1", "adv2",
             "mean", "var", "kurt", "spec", "cyclo", "pwr", "pnorm", "div", "ks", "cov",
             # --cnn-adversary / --views rows; empty strings when those flags are off
             "D_cnn", "D_psd", "D_tf", "A_cnn", "A_psd", "A_tf",
             "cnn_acc", "psd_acc", "tf_acc",
             "ber_link", "ber5", "ks_p", "entropy", "circ", "papr", "scf", "c42",
             "wvd", "Sc", "n_pass", "gate"])
    tb = None
    try:
        from torch.utils.tensorboard import SummaryWriter
        tb = SummaryWriter(args.tb)
    except Exception:                                     # pragma: no cover
        pass
    wb = None
    if args.wandb:
        try:
            import wandb
            wb = wandb
            wandb.init(project=args.wandb, config=cfg.to_dict(),
                       name=os.path.basename(args.out))
        except Exception as e:                              # pragma: no cover
            print(f"[wandb] disabled ({e})")

    d_stop = max(1, int(args.d_stop_frac * args.epochs))
    print(f"[cfg] wardens trained for epochs 1..{d_stop}, frozen afterwards")
    best = -1e18 if resume_best is None else resume_best
    t0 = time.time()
    with open(log, "a", newline="") as lf:
        wr = csv.DictWriter(lf, fieldnames=cols)
        if new_log:
            wr.writeheader()

        for ep in range(start, args.epochs + 1):
            G.train(); D.train()
            ramp = 0.0 if ep <= args.warmup else min(1.0, (ep - args.warmup) / 10.0)
            acc: Dict[str, float] = {}

            for _step in range(args.steps):
                b = (torch.rand(args.batch, cfg.n_bits, device=device) > 0.5).float() * 2 - 1
                z = torch.randn(args.batch, cfg.z_dim, device=device)

                # ---------- wardens: gen vs (AWGN [+ real captures]) ----------
                with torch.no_grad():
                    fake = G(z, b)
                real = torch.randn(args.batch, 2, cfg.frame_len, device=device)
                real = real / real.reshape(real.shape[0], -1).pow(2).mean(1, keepdim=True
                                                                          ).add(1e-12).sqrt().view(-1, 1, 1)
                rb = bank.sample(args.batch // 2, cfg.frame_len, device)
                if rb is not None:
                    real[: rb.shape[0]] = rb
                if ep <= d_stop:
                    dl1 = d_train_step(W1, fake, real, optW)
                    dl2 = d_train_step(W2, fake, real, optW)
                else:                                  # frozen detector regime
                    with torch.no_grad():
                        _lg = torch.cat([W1(fake).flatten(), W1(real).flatten()])
                        dl1 = float(F.binary_cross_entropy_with_logits(
                            _lg,
                            torch.cat([torch.zeros(fake.shape[0], device=_lg.device),
                                       torch.ones(real.shape[0], device=_lg.device)], 0)))
                        dl2 = dl1
                # the cat-and-mouse: every co-trained detector takes its own step
                # on the same (fake, real) pair, and freezes on the same schedule
                dlx = (extra.train_step(fake, real, trainable=ep <= d_stop)
                       if extra is not None else {})

                # ---------- generator + decoder ----------
                z = torch.randn(args.batch, cfg.z_dim, device=device)
                x = G(z, b)
                y, _ = chan(x)
                logits = D(y)
                l_rec = F.binary_cross_entropy_with_logits(logits, (b > 0.5).float())

                l1 = warden_loss(W1(x)); l2 = warden_loss(W2(x))
                x_terms = extra.gen_terms(x) if extra is not None else {}
                ref = torch.randn_like(x)
                ref = ref / ref.reshape(ref.shape[0], -1).pow(2).mean(1, keepdim=True
                                                                      ).add(1e-12).sqrt().view(-1, 1, 1)
                # nine-component statistical objective (paper Table 1 weights)
                stat, terms = composite_stat_loss(x, ref, z, w_cov=args.w_cov)

                L_G = (args.w_rec * l_rec
                       + ramp * args.w_adv * (l1 + 0.5 * l2)
                       + ramp * args.w_stat * stat
                       + ramp * sum(x_terms.values()))
                optG.zero_grad(); optD.zero_grad()
                L_G.backward()
                torch.nn.utils.clip_grad_norm_(G.parameters(), 3.0)
                torch.nn.utils.clip_grad_norm_(D.parameters(), 3.0)
                optG.step(); optD.step()
                D.sync_code()

                row_acc = dict(loss_G=L_G, bce=l_rec, adv1=l1, adv2=l2,
                               D1=dl1, D2=dl2)
                row_acc.update(dlx)                       # D_cnn / D_psd / D_tf
                row_acc.update({k: v for k, v in x_terms.items()})   # A_* generator side
                row_acc.update({k: v for k, v in terms.items()})
                for k, v in row_acc.items():
                    acc[k] = acc.get(k, 0.0) + float(v if not torch.is_tensor(v)
                                                     else v.detach()) / args.steps

            # D2 refresh (anti-fingerprint defence 3)
            if ep % 25 == 24:
                W2 = Warden(**warden_kwargs).to(device)
                W2._init_kwargs = warden_kwargs
                optW = torch.optim.Adam(list(W1.parameters()) + list(W2.parameters()),
                                        lr=1e-4, betas=(0.5, 0.999))
                print("  [D2] re-initialised (periodic adversary refreshment)")
            if extra is not None:
                extra.refresh_if_due(ep)

            # ---------------- metrics on a fresh held-out batch ----------------
            G.eval(); D.eval()
            with torch.no_grad():
                nb = 1024
                bb = (torch.rand(nb, cfg.n_bits, device=device) > 0.5).float() * 2 - 1
                zz = torch.randn(nb, cfg.z_dim, device=device)
                xx = G(zz, bb)
                m = ew_report(xx.cpu().numpy(),
                              np.random.randn(nb, 2, cfg.frame_len).astype(np.float32))
                yb, _ = chan(xx, snr_db=cfg.eval_snr)
                ber5 = float((D(yb) > 0).float().ne((bb > 0.5).float()).float().mean())
                # full-link BER: pilot sync in numpy, exactly the field path
                ber_link = link_ber(G, D, cfg, device, n_frames=256, snr_db=cfg.eval_snr,
                                    field=field)
                adv = warden_acc(W1, G, cfg, device, n=800)
                xacc = {}
                if extra is not None:
                    # same (real, fake) recipe warden_acc uses, so the numbers
                    # next to `adv` in the CSV are comparable to it
                    half = 400
                    fake_e = G(torch.randn(half, cfg.z_dim, device=device),
                               (torch.rand(half, cfg.n_bits, device=device) > 0.5
                                ).float() * 2 - 1)
                    real_e = torch.randn(half, 2, cfg.frame_len, device=device)
                    real_e = real_e / real_e.reshape(half, -1).pow(2).mean(1, keepdim=True
                                                                           ).add(1e-12).sqrt().view(-1, 1, 1)
                    xacc = extra.accuracy(fake_e, real_e)
            gate = ("PASS" if (m["ks_p"] > GATE["ks"] and adv <= GATE["adv"]
                               and ber_link <= GATE["ber"]) else "FAIL")

            row = dict(epoch=ep, sec=int(time.time() - t0),
                       **{k: round(v, 6) for k, v in acc.items()},
                       ber5=round(ber5, 7), ber_link=round(ber_link, 7),
                       ks_p=round(m["ks_p"], 4), entropy=round(m["entropy"], 4),
                       circ=round(m["circ"], 4), papr=round(m["papr"], 3),
                       scf=round(m["scf"], 3), c42=round(m["c42"], 4),
                       wvd=round(m["wvd"], 3), Sc=round(m["Sc"], 4),
                       n_pass=m["n_pass"], gate=gate)
            row.update({f"{k}_acc": round(v, 3) for k, v in xacc.items()})  # cnn/psd/tf
            wr.writerow(row); lf.flush()
            if tb:
                for k, v in row.items():
                    if isinstance(v, (int, float)):
                        tb.add_scalar(k, v, ep)
            if wb:
                wb.log(row)
            print(f"[ep {ep:4d}] G {row['loss_G']:.3f} bce {row['bce']:.5f} | "
                  f"D1 {row['D1']:.3f} D2 {row['D2']:.3f} | adv {adv:.1f}% | "
                  f"KS p {m['ks_p']:.3f} kurt {m['kurt']:.3f} H {m['entropy']:.3f} "
                  f"circ {m['circ']:.3f} | BER5 {ber5:.2e} link {ber_link:.2e} | "
                  f"EW {m['n_pass']}/8 Sc {m['Sc']:.3f} -> {gate}", flush=True)
            if xacc:
                print("  [adversary] " + " ".join(f"{k} {v:.1f}%"
                                                  for k, v in xacc.items()), flush=True)

            met = dict(adv=round(adv, 2), ks_p=round(m["ks_p"], 4),
                       ber5=round(ber5, 7), ber_link=round(ber_link, 7),
                       Sc=round(m["Sc"], 4), n_pass=m["n_pass"], gate=gate)
            # Only epochs in the FROZEN-warden regime are eligible for "best":
            # before the freeze, a fresh (half-trained) warden trivially sits at
            # 50 %, so an unqualified score would always pick epoch 1-2 and call
            # it stealth.  adv is only meaningful once D has been trained to
            # convergence and then frozen while G keeps pushing it back.
            eligible = ep > d_stop + 2 or args.d_stop_frac >= 1.0
            score = (m["n_pass"] * 100 + 100 * min(m["ks_p"], 1.0)
                     - 10000 * max(0.0, ber_link - GATE["ber"])
                     - 10.0 * max(0.0, abs(adv - 52.0) - 4.0)
                     - (0.0 if gate == "PASS" else 250.0)) if eligible else -1e18
            # score/best settle BEFORE the checkpoint write so the stored
            # ``best`` field is current for --resume (previously the main save
            # lagged the update by one best epoch)
            is_best = score > best
            if is_best:
                best = score
            torch.save(dict(epoch=ep, cfg=cfg.to_dict(), metrics=met, best=best,
                            generator=G.state_dict(), decoder=D.state_dict(),
                            warden1=W1.state_dict(), warden2=W2.state_dict(),
                            optG=optG.state_dict(), optD=optD.state_dict(),
                            field=(args.field_preset if args.field else ""),
                            detectors=(extra.state_dict() if extra is not None else None)),
                       args.out)
            if is_best:
                torch.save(dict(epoch=ep, cfg=cfg.to_dict(), metrics=met,
                                generator=G.state_dict(), decoder=D.state_dict(),
                                warden1=W1.state_dict(), warden2=W2.state_dict(),
                                field=(args.field_preset if args.field else ""),
                                detectors=(extra.state_dict() if extra is not None else None)),
                           args.out.replace(".pt", ".best.pt"))
                export_for_grc(args.out.replace(".pt", ".best.pt"), device,
                                 args.export_dir or None)
                save_config(cfg, args.out.replace(".pt", ".best.json"))
                print(f"  [best] score {score:.1f} -> {args.out.replace('.pt', '.best.pt')}")
            if args.export_every and ep % args.export_every == 0:
                # a mid-run peek, in a subfolder: the blocks load run/generator_lpi.pt,
                # so writing the *current* epoch over the *best* one would be a lie
                peek = os.path.join(_export_dir(args), "intermediate")
                export_for_grc(args.out, device, peek)

        print(f"\n[done] {args.epochs} epochs in {(time.time()-t0)/60:.1f} min")
        best_ckpt = args.out.replace(".pt", ".best.pt")
        if os.path.exists(best_ckpt):
            # the last thing a run does is make run/ match its own best snapshot --
            # an --export-every peek or an interrupted loop cannot leave drift
            export_for_grc(best_ckpt, device, _export_dir(args))
        print(f"[done] best snapshot: {best_ckpt}")
        # a hint the user follows must be a command that exists -- `link_test.py`
        # never did (lpi_v4/check_docs.py now fails the build if one rots again)
        print(f"[done] next: python lpi_eval.py --ckpt {best_ckpt} --frames 512 "
              f"--fit-warden 800 --md run/eval.md --out-json run/eval.json")
        print("[done] then, with no radio attached: python rx_usrp.py --selftest")
    if tb:
        tb.close()


# =========================================================================
@torch.no_grad()
def warden_acc(W: Warden, G, cfg: LPIConfig, device, n: int = 800) -> float:
    """Balanced accuracy of the trained warden on fresh generator output."""
    W.eval()
    half = n // 2
    b = (torch.rand(half, cfg.n_bits, device=device) > 0.5).float() * 2 - 1
    fake = G(torch.randn(half, cfg.z_dim, device=device), b)
    real = torch.randn(half, 2, cfg.frame_len, device=device)
    real = real / real.reshape(half, -1).pow(2).mean(1, keepdim=True).add(1e-12).sqrt().view(-1, 1, 1)
    p = torch.sigmoid(W(fake)).flatten()          # ->1 means 'this is a fake'
    q = torch.sigmoid(W(real)).flatten()          # ->0 means 'this is real'
    acc = float(((1 - p.float()).mean() + q.float().mean()) * 50.0)
    # A warden can swap its own output labels for free, so the number that matters
    # is the best it can do in either orientation.  Reporting 3 % instead of 97 %
    # would flatter the generator enormously.
    return float(max(acc, 100.0 - acc))


@torch.no_grad()
def link_ber(G, D, cfg: LPIConfig, device, n_frames: int = 256, snr_db: float = 5.0,
             key: str = "SESSION-KEY", seed: int = 7, field=None) -> float:
    """BER of the *whole* receive chain: preamble timing + CFO + phase, then the
    neural decoder.  This is the number that matters for the field test -- the
    in-graph numbers can look perfect while sync is broken.

    ``field`` (a dict from ``lpi_field.field_preset``) puts the same multipath,
    Doppler and fractional timing the trainer used in front of the noise, so the
    gate reads the channel the model was actually trained for instead of a
    bench-clean one.  None (default) is the original chain, unchanged.
    """
    rng = np.random.default_rng(seed)
    g = torch.Generator(device="cpu").manual_seed(seed)
    b = (torch.rand(n_frames, cfg.n_bits, generator=g) > 0.5).float() * 2 - 1
    x = G(torch.randn(n_frames, cfg.z_dim, generator=g).to(device), b.to(device))
    # assemble the complex envelope on CPU: MPS (torch 2.2) has no complex
    # arithmetic support and we need numpy right after anyway.
    x_cpu = x.cpu()
    pay = (x_cpu[:, 0] + 1j * x_cpu[:, 1]).numpy().astype(np.complex64)
    pil = make_preamble(key, cfg.pilot_len, cfg.fs)
    fr = frame_with_pilot(pay, pil).reshape(-1)
    if field is not None:
        from lpi_field import apply_field_np
        fr = apply_field_np(fr.astype(np.complex128), cfg, field, rng).astype(np.complex64)
    fs = cfg.fs
    n = fr.size
    cfo = float(rng.uniform(-120, 120)); phi0 = float(rng.uniform(0, 2 * np.pi))
    t = np.arange(n) / fs
    cap = fr * (0.33 * np.exp(1j * (2 * np.pi * cfo * t + phi0)))
    cap = cap + (0.01 + 0.015j)
    snr = 10 ** (snr_db / 20.0)
    cap = cap + np.abs(cap).std() / snr / np.sqrt(2) * (
        rng.standard_normal(n) + 1j * rng.standard_normal(n))
    pad = int(rng.integers(0, 4 * cfg.total_len))
    cap = np.concatenate([np.zeros(pad, np.complex64), cap.astype(np.complex64),
                          np.zeros(1024, np.complex64)])
    v = sync_and_correct(cap, cfg, pil)
    got = (D(torch.from_numpy(v).to(device)) > 0).cpu().numpy().reshape(-1)
    exp = (b.numpy() > 0.5).reshape(-1)
    m = min(len(got), len(exp))
    return float(np.mean(got[:m] != exp[:m])) if m else 1.0


# =========================================================================
def _export_dir(args) -> str:
    """Where the canonical TorchScript pair goes (default: beside --out, i.e. run/)."""
    return args.export_dir or os.path.dirname(os.path.abspath(args.out))


def export_for_grc(ckpt: str, device: str = "cpu", outdir: str | None = None) -> None:
    """TorchScript export for the GNU Radio Python blocks / the USRP scripts."""
    outdir = outdir or os.path.dirname(os.path.abspath(ckpt))
    os.makedirs(outdir, exist_ok=True)
    # This runs *inside* the epoch loop, on every improvement, and tracing needs
    # dummy tensors -> torch.randn.  Left alone, that quietly advances the global
    # RNG and changes which samples the next epoch draws: adding a print() to the
    # exporter would then alter the trained model.  It is why a CI smoke run crossed
    # its own KS threshold between two commits (FINDINGS.md), so the stream is
    # saved and restored around the whole export.
    rng = (torch.get_rng_state(), np.random.get_state(), random.getstate())
    try:
        # jit-tracing over MPS would bake MPS kernels into the artifact the GNU
        # Radio blocks load on the *host* CPU -- and linalg.solve (the ZF
        # detector) has no MPS implementation at all, so the trace would need
        # PYTORCH_ENABLE_MPS_FALLBACK at RX time.  Export always on the CPU; it
        # runs once per best epoch, so the cost is noise.
        return _export_for_grc(ckpt, "cpu" if device == "mps" else device, outdir)
    finally:
        torch.set_rng_state(rng[0])       # a ByteTensor, not a tuple: index it once
        np.random.set_state(rng[1])
        random.setstate(rng[2])


def _export_for_grc(ckpt: str, device: str, outdir: str | None) -> None:
    ck = torch.load(ckpt, map_location=device, weights_only=False)
    cfg = LPIConfig(**{k: (tuple(v) if k == "snr_range" else v)
                       for k, v in ck.get("cfg", {}).items()})
    G = LPIGenerator(cfg).to(device).eval(); G.load_state_dict(ck["generator"])
    D = LPIDecoder(cfg).to(device).eval(); D.load_state_dict(ck["decoder"])
    z = torch.randn(2, cfg.z_dim, device=device)
    b = (torch.rand(2, cfg.n_bits, device=device) > 0.5).float() * 2 - 1
    y = torch.randn(2, 2, cfg.frame_len, device=device)
    with torch.no_grad():
        # check_trace=False on purpose: the generator draws fresh masking noise on
        # every call (that IS the design), so two calls cannot produce the same
        # tensor and the tracer's equality check would always fail.
        gg = torch.jit.trace(G, (z, b), check_trace=False)
        dd = torch.jit.trace(D, (y,), check_trace=False)
    gg.save(os.path.join(outdir, "generator_lpi.pt"))
    dd.save(os.path.join(outdir, "decoder_lpi.pt"))
    save_config(cfg, os.path.join(outdir, "lpi_config.json"))
    # A mirror is only honest while it is a mirror: record the bytes it came from so
    # `run/generator_lpi.pt` can never silently be from another epoch than the
    # checkpoint the metrics were measured on (that happened once -- see FINDINGS).
    with open(ckpt, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    with open(os.path.join(outdir, "export_manifest.json"), "w") as fh:
        json.dump({"exported_from": os.path.basename(ckpt), "sha256": digest,
                   "epoch": ck.get("epoch"),
                   "files": ["generator_lpi.pt", "decoder_lpi.pt", "lpi_config.json"]},
                  fh, indent=1)
    print(f"[export] generator_lpi.pt + decoder_lpi.pt + lpi_config.json -> {outdir}"
          f"  (from {os.path.basename(ckpt)}, epoch {ck.get('epoch')}, sha256 {digest[:12]})")


if __name__ == "__main__":
    main()
