#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lpi_adversary.py -- the hostile EW receiver's CNN, inside the training loop.
===========================================================================

Two detectors live in this repo and they answer different questions:

  * ``Warden`` (lpi_core) is the *paper's* adversary: is this frame noise, yes
    or no?  The v4 trainer runs two of them, W2 with its weights reinitialised
    every 25 epochs, and freezes both for the final third of the run.
  * ``RadioML_VTCnn2`` (lpi_research/gan/adversary_cnn.py) is the *EW
    operator's* receiver: the VT-CNN2 from the RadioML literature, trained
    after the fact to answer "which of these is an LPI signal?".  It was only
    ever run as a **post-hoc evaluation**, so the generator never had to beat
    a *learning* detector -- it beat a fixed one and the number was written
    down after the fight was over.

This module moves the second one into the loop.  The generator and the CNN
adversary now co-train: the CNN gets a cross-entropy step against (AWGN,
generator) every minibatch, the generator is pushed toward a coin flip on the
CNN's logit every minibatch, and the CNN's weights are thrown away and
redrawn every ``cnn_refresh`` epochs so the generator cannot overfit one
detector's fingerprint.  The cat-and-mouse, with both animals moving.

``DetectorBank`` holds any number of these detectors -- the CNN and/or the
PSD/TF warden views -- each with its own optimizer and refresh cadence, so
``lpi_train`` can stay a loop instead of becoming a state machine.

The generator-vs-detector objective (``warden_loss``) is **moved here** from
``lpi_train``: one definition, not two.  ``lpi_train`` keeps importing the
name, so nothing that did ``from lpi_train import warden_loss`` changes.

MPS note: everything in this module is conv/fc/dropout/BCE/CE -- all supported
on torch 2.2 MPS.  The *warden views* (PSD/TF) go through ``torch.fft`` which
is not, which is why ``PYTORCH_ENABLE_MPS_FALLBACK=1`` is set at the top of
``lpi_train`` before torch is imported.
"""
from __future__ import annotations

from typing import Callable, Dict, Iterable, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from lpi_core import LPIConfig, Warden


def warden_loss(w: torch.Tensor, target: float = 0.5, dead: float = 0.02) -> torch.Tensor:
    """Drive Pr[D(x)=1] -> 0.5 with a dead zone at +-0.02 around target.

    Why not BCE-to-0.5: BCE on a *target* of 0.5 is not a GAN.  Its gradient
    vanishes as the detector becomes confident, so the generator stalls right
    where the warden is strongest.  The hinge keeps ~full slope out to +-0.02,
    which is the paper's stated formulation and the reason this trains at all.
    """
    return (torch.sigmoid(w) - target).abs().sub(dead).clamp_min(0.0).pow(2).mean()


class VTCNN2(nn.Module):
    """RadioML VT-CNN2 (O'Shea et al.), faithful to lpi_research's port.

    Input  (B, 2, seq_len) real-ified I/Q.  Output (B, 2) logits: row 0 =
    "AWGN", row 1 = "signal".  ``seq_len`` is parameterised (not hard-coded 512)
    so it matches ``cfg.frame_len`` and survives a framing change.

    ~1.0 M parameters at seq_len=512, dominated by fc1 (16*512 -> 128).  That
    fully-connected tail is what makes it a *hard* adversary rather than a
    spectrogram CNN: it learns sample-position-specific fingerprints, which is
    exactly the kind of tell a generator that only optimises FFT statistics
    leaves behind.
    """

    def __init__(self, seq_len: int = 512, in_channels: int = 2, num_classes: int = 2):
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, 64, kernel_size=7, padding=3)
        self.conv2 = nn.Conv1d(64, 16, kernel_size=7, padding=3)
        self.fc1 = nn.Linear(16 * seq_len, 128)
        self.dropout = nn.Dropout(0.5)
        self.fc2 = nn.Linear(128, num_classes)
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.relu(self.conv1(x))
        h = self.relu(self.conv2(h))
        h = h.reshape(h.size(0), -1)
        h = self.dropout(self.relu(self.fc1(h)))
        return self.fc2(h)


def adversary_train_step(model: nn.Module, fake: torch.Tensor, real: torch.Tensor,
                         opt: torch.optim.Optimizer) -> float:
    """One cross-entropy step: real(AWGN) = class 0, generator = class 1."""
    was_training = model.training
    model.train()
    x = torch.cat([real.detach(), fake.detach()], dim=0)
    y = torch.cat([torch.zeros(real.shape[0], dtype=torch.long, device=x.device),
                   torch.ones(fake.shape[0], dtype=torch.long, device=x.device)])
    opt.zero_grad()
    loss = F.cross_entropy(model(x), y)
    loss.backward()
    opt.step()
    if not was_training:
        model.eval()
    return float(loss.detach())


@torch.no_grad()
def _balanced_acc(model: nn.Module, fake: torch.Tensor, real: torch.Tensor) -> float:
    """Balanced accuracy in %, orientation-proof (same rule as lpi_train.warden_acc).

    A detector may swap its own class labels for free, so the number reported
    is the *better* of the two orientations -- never the flattering one.  That
    max() also makes the two detectors' opposite label conventions (VT-CNN2
    trains real=0/fake=1; the lpi_core Warden trains fake=0/real=1) irrelevant:
    each one's "wrong" formula is the other's, and max(A, 100-A) is the same
    either way.

    Handles both output shapes: VT-CNN2 returns (B, 2) logits and uses row 1
    ("signal"), the lpi_core Warden returns a single (B, 1) logit.
    """
    model.eval()
    of, or_ = model(fake), model(real)
    if of.dim() == 2 and of.shape[1] >= 2:
        p = torch.sigmoid(of[:, 1].float()).mean()
        q = torch.sigmoid(or_[:, 1].float()).mean()
    else:
        p = torch.sigmoid(of.reshape(-1).float()).mean()
        q = torch.sigmoid(or_.reshape(-1).float()).mean()
    acc = float(((1.0 - p) + q) * 50.0)
    return float(max(acc, 100.0 - acc))


class DetectorBank:
    """Every hostile detector the generator must fool *besides* W1/W2.

    Each member owns its optimizer and refresh cadence:

      * kind ``"cnn"``  -- VT-CNN2, cross-entropy step, refreshed every
        ``cnn_refresh`` epochs (a *fresh cat* every N rounds).
      * kind ``"warden"`` -- a lpi_core ``Warden`` on the ``psd`` or ``tf``
        view, stepped with BCE and refreshed every ``view_refresh`` epochs
        (matching the trainer's own W2 cadence of 25).

    ``iq`` in ``views`` is accepted and ignored: W1/W2 already own that view in
    the trainer, and a third identical detector would only triple the compute.

    Refresh mirrors the trainer's W2 rule -- ``epoch % cadence == cadence - 1``
    -- so W2, the PSD view and the CNN all get re-drawn on their own clocks.
    """

    def __init__(self, cfg: LPIConfig, device: str = "cpu",
                 views: Iterable[str] = (), cnn: bool = False,
                 cnn_refresh: int = 10, view_refresh: int = 25,
                 w_cnn: float = 1.0, lr: float = 1e-4):
        self.cfg = cfg
        self.device = device
        self._items: list[Dict] = []
        for view in views:
            v = str(view).strip().lower()
            if not v or v == "iq":
                continue
            if v not in ("psd", "tf"):
                raise ValueError(f"unknown warden view {v!r}; use iq, psd, tf")
            self._add(f"{v}",
                      lambda v=v: Warden(n_fft=cfg.frame_len, input=v, ch=cfg.ch),
                      "warden", int(view_refresh), lr, 1.0)
        if cnn:
            self._add("cnn", lambda: VTCNN2(seq_len=cfg.frame_len),
                      "cnn", int(cnn_refresh), lr, float(w_cnn))

    # -- construction -------------------------------------------------------
    def _add(self, name: str, factory: Callable[[], nn.Module], kind: str,
             cadence: int, lr: float, w: float) -> None:
        model = factory().to(self.device)
        self._items.append({
            "name": name, "kind": kind, "cadence": int(cadence), "w": float(w),
            "lr": float(lr), "factory": factory, "model": model,
            "opt": torch.optim.Adam(model.parameters(), lr=lr, betas=(0.5, 0.999)),
        })

    @property
    def names(self):
        return [it["name"] for it in self._items]

    def __len__(self) -> int:
        return len(self._items)

    # -- the loop's three hooks --------------------------------------------
    def train_step(self, fake: torch.Tensor, real: torch.Tensor,
                   trainable: bool = True) -> Dict[str, float]:
        """One step of every detector.  No-op (returns {}) when frozen, so the
        trainer's ``ep <= d_stop`` protocol extends to the whole bank."""
        out: Dict[str, float] = {}
        if not trainable or not self._items:
            return out
        for it in self._items:
            if it["kind"] == "cnn":
                out["D_" + it["name"]] = adversary_train_step(
                    it["model"], fake, real, it["opt"])
            else:
                m = it["model"]
                m.train()
                it["opt"].zero_grad()
                logits = torch.cat([m(fake).flatten(), m(real).flatten()])
                labels = torch.cat([torch.zeros(fake.shape[0]),
                                    torch.ones(real.shape[0])]).to(logits.device)
                loss = F.binary_cross_entropy_with_logits(logits, labels.float())
                loss.backward()
                it["opt"].step()
                out["D_" + it["name"]] = float(loss.detach())
        return out

    def gen_terms(self, fake: torch.Tensor) -> Dict[str, torch.Tensor]:
        """The generator-side objective for every detector, weighted.

        Dropout stays *on* inside the CNN during the generator's step (the
        detector is in train mode).  That is deliberate: a stochastic detector
        is a target the generator cannot memorise, which is the whole point of
        the mouse getting to move.
        """
        out: Dict[str, torch.Tensor] = {}
        for it in self._items:
            m = it["model"]
            if it["kind"] == "cnn":
                out["A_" + it["name"]] = it["w"] * warden_loss(m(fake)[:, 1])
            else:
                out["A_" + it["name"]] = it["w"] * warden_loss(m(fake))
        return out

    def refresh_if_due(self, epoch: int, log=print) -> None:
        """Re-draw every detector whose cadence is due (the fresh-cat rule)."""
        for it in self._items:
            c = it["cadence"]
            if c > 0 and epoch % c == c - 1:
                fresh = it["factory"]().to(self.device)
                it["model"] = fresh
                it["opt"] = torch.optim.Adam(fresh.parameters(), lr=it["lr"],
                                             betas=(0.5, 0.999))
                log(f"  [adversary] {it['name']} re-initialised (cadence {c})")

    @torch.no_grad()
    def accuracy(self, fake: torch.Tensor, real: torch.Tensor) -> Dict[str, float]:
        """Orientation-proof balanced accuracy per detector (%)."""
        return {it["name"]: _balanced_acc(it["model"], fake, real)
                for it in self._items}

    # -- persistence (best-effort; a stale detector must not kill a resume) --
    def state_dict(self) -> Dict[str, Dict]:
        return {it["name"]: it["model"].state_dict() for it in self._items}

    def load_state_dict(self, sd: Optional[Dict], strict: bool = False) -> None:
        if not sd:
            return
        for it in self._items:
            s = sd.get(it["name"])
            if s is not None:
                try:
                    it["model"].load_state_dict(s, strict=strict)
                except Exception as e:      # noqa: BLE001 - resume must never die here
                    print(f"  [adversary] {it['name']} state not restored: {e}")
