#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lpi_datasets.py -- optional real-world reference signals for warden training.
============================================================================

The generator's invisibility is only meaningful if the adversary it is trained
against has seen *real* captures, not just synthetic noise.  This module loads a
bounded random subset of either

  * DeepSig GOLD   GOLD_XYZ_OSC.0001_1024.hdf5   (X: (N,1024,2) float32), or
  * DeepSig RML    RML2018.01A.pkl               ({(mod,snr): (N,1024,2)})

and hands the trainer an (M, 2, frame_len) bank.  It never loads the whole file:
21 GB of HDF5 is read in sorted chunks, and only ~20k frames are kept.

If nothing is found the trainer degrades gracefully to AWGN-only wardens (that is
exactly the behaviour the reference paper's ablation calls "sim-only detector").
"""
from __future__ import annotations

import glob
import os
import pickle

import numpy as np


def find_data_file(explicit: str | None = None, cwd: str = ".") -> str | None:
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    pats = ["*.hdf5", "*/*.hdf5", "*.h5", "*/*.h5", "*RML*.pkl", "*/*.pkl"]
    hits = []
    for p in pats:
        hits += [h for h in glob.glob(os.path.join(cwd, p)) if os.path.isfile(h)]
    hits = sorted(set(hits), key=os.path.getsize)
    return hits[-1] if hits else None


def _norm(a: np.ndarray) -> np.ndarray:
    m = a.mean(axis=-1, keepdims=True)
    v = a.std(axis=-1, keepdims=True)
    return (a - m) / np.where(v > 0, v, 1.0)


def load_hdf5(path: str, n_take=20000, target_len=512, seed=1234) -> np.ndarray:
    """Read ``n_take`` random (2, target_len) frames out of a GOLD/RML-style HDF5.

    Both real-world layouts are accepted -- GOLD ships ``(N, T, 2)`` and most
    self-made files are ``(N, 2, T)`` -- and the time axis is sliced with a
    random start so a 1024-sample capture yields several distinct 512-sample
    frames rather than always its first half.

    A note on why this function used to raise for *every* file: the old
    transpose test looked at ``shape[1] == 2`` and then transposed anyway
    (turning a correct (k,2,T) into an unusable (k,T,2)), while leaving the
    (k,T,2) layout it was meant to fix untouched -- so ``chunk[j][:, st:...]``
    always sliced the 2-wide channel axis and blew up with
    ``could not broadcast input array from shape (1024,2) into shape (2,512)``.
    ``find_and_load_real`` swallowed that error and the trainer carried on
    "AWGN only" behind a ``--radioml`` flag, which is the single worst failure
    mode a metric can have: it looks trained against a real adversary and is
    not.  tests/test_lpi_field.py pins both layouts now.
    """
    import h5py
    print(f"[data] GOLD {path} ...")
    rng = np.random.default_rng(seed)
    with h5py.File(path, "r") as f:
        key = "X" if "X" in f else list(f.keys())[0]
        X = f[key]
        N = X.shape[0]
        idx = np.sort(rng.choice(N, size=min(n_take, N), replace=False))
        out = np.empty((len(idx), 2, target_len), dtype=np.float32)
        for s in range(0, len(idx), 2000):
            sel = idx[s:s + 2000]
            chunk = np.asarray(X[sel])                    # (k,T,2) or (k,2,T)
            if chunk.shape[-1] != 2 and chunk.shape[1] == 2:
                chunk = np.transpose(chunk, (0, 2, 1))    # (k,2,T) -> (k,T,2)
            elif chunk.shape[-1] != 2:
                raise ValueError(f"expected an (k,T,2) or (k,2,T) array in {path}, "
                                 f"got {chunk.shape}")
            for j in range(len(sel)):
                n_time = chunk.shape[1]
                st = int(rng.integers(0, max(1, n_time - target_len + 1)))
                seg = chunk[j][st:st + target_len]        # (<=target_len, 2)
                if seg.shape[0] < target_len:             # capture shorter than a frame
                    seg = np.pad(seg, ((0, target_len - seg.shape[0]), (0, 0)))
                out[s + j] = np.transpose(seg, (1, 0))    # (2, target_len)
    print(f"[data] GOLD: {out.shape} frames from {N:,} captures")
    return _norm(out).astype(np.float32)


def load_pkl(path: str, n_take=20000, target_len=512) -> np.ndarray:
    print(f"[data] RML2018 {path} ...")
    with open(path, "rb") as f:
        data = pickle.load(f, encoding="latin1")
    out = []
    for (_mod, _snr), arr in data.items():
        a = np.asarray(arr, dtype=np.float32)          # (N,1024,2)
        if a.ndim != 3:
            continue
        a = np.transpose(a, (0, 2, 1))
        st = np.random.randint(0, max(1, a.shape[-1] - target_len + 1))
        out.append(a[:, :, st:st + target_len])
        if sum(len(o) for o in out) > n_take:
            break
    x = np.concatenate(out, 0)[:n_take]
    print(f"[data] RML2018: {x.shape}")
    return _norm(x).astype(np.float32)


def find_and_load_real(n_real: int, target_len: int = 512, explicit: str | None = None,
                       cwd: str = ".") -> np.ndarray | None:
    path = find_data_file(explicit, cwd)
    if path is None:
        return None
    try:
        if path.endswith((".hdf5", ".h5")):
            return load_hdf5(path, n_real, target_len)
        return load_pkl(path, n_real, target_len)
    except Exception as e:                                  # noqa: BLE001
        print(f"[data] {path} unreadable ({e}); continuing with AWGN only")
        return None


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else find_data_file()
    print("found:", p)
    if p:
        a = find_and_load_real(2000, explicit=p)
        print(a.shape, a.mean(), a.std(), a.min(), a.max())
