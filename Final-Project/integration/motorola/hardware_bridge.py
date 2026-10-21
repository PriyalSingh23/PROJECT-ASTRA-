"""Motorola MOTOTRBO hardware bridge — safe, pluggable, Raspberry Pi ready.

The simulator in ``integration/motorola/adapter.py`` proves the *protocol*
contract (280-byte DMR ceiling, TMS framing, signed ACK reconciliation). This
module is the *physical* half: it turns an approved dispatch into bytes on a
real radio path.

Three backends are provided, in order of recommended use:

1. ``SoundCardBackend`` — the recommended field-pilot path (and what ``auto``
   selects). Radio in analogue (or DMR voice) mode, 3.5mm/2.5mm audio into a
   cheap USB sound card, PTT driven by a GPIO pin through an opto-isolator. The
   Pi keys PTT, plays a modulated audio burst (``voice_modem.VoiceModem``), and
   the far end records and demodulates. This makes *any* radio a byte pipe and
   needs no vendor protocol, no CPS, and no radio programming at all.

2. ``MnisUdpBackend`` — MOTOTRBO Network Interface Service (MNIS).
   The vendor-documented IP path; use it when MOTOTRBO infrastructure already
   exists. A radio (or repeater) is connected to a host over USB/IP; MOTOTRBO
   Network Interface Service (part of the MOTOTRBO CPS / Radio Management
   family) exposes the radio's data services as UDP sockets (commonly 4000/4001
   for control + data). The host — which can be a Raspberry Pi — sends TMS data
   PDUs to MNIS, which transmits them. It is never auto-selected: a UDP
   ``connect()`` cannot prove MNIS is listening, so auto-selecting it could
   transmit into the void and report success.

3. ``GpioPttBackend`` — same PTT discipline, but the payload goes out over a
   UART/serial link instead of audio. Useful when the radio exposes a data
   port, or for bench work with a wired link.

SAFETY: nothing here transmits unless ``MOTOROLA_RADIO_APPROVED=true`` is set
*and* a valid frequency/station licence exists. With the flag unset the bridge
runs in dry-run mode and returns what it *would* have sent. This mirrors the
STAR-V lockout philosophy: an unapproved radio is a bug, not a feature.
"""
from __future__ import annotations

import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from integration.motorola.voice_modem import ModemConfig, VoiceModem, audio_levels, write_wav

DMR_MAX_PAYLOAD_BYTES = 280  # DMR Tier II data ceiling enforced by the adapter
DEFAULT_MNIS_HOST = os.environ.get("MOTOROLA_MNIS_HOST", "127.0.0.1")
DEFAULT_MNIS_PORT = int(os.environ.get("MOTOROLA_MNIS_PORT", "4001"))
DEFAULT_PTT_GPIO_PIN = int(os.environ.get("MOTOROLA_PTT_GPIO", "17"))
DEFAULT_SERIAL_PORT = os.environ.get("MOTOROLA_SERIAL_PORT", "/dev/ttyUSB0")
DEFAULT_AUDIO_OUT = os.environ.get("MOTOROLA_AUDIO_OUT", "default")
DEFAULT_AUDIO_IN = os.environ.get("MOTOROLA_AUDIO_IN", "default")
DEFAULT_AUDIO_FS = int(os.environ.get("MOTOROLA_AUDIO_FS", "48000"))
DEFAULT_PTT_LEAD_MS = int(os.environ.get("MOTOROLA_PTT_LEAD_MS", "250"))
DEFAULT_PTT_TAIL_MS = int(os.environ.get("MOTOROLA_PTT_TAIL_MS", "150"))


def _is_approved() -> bool:
    return os.environ.get("MOTOROLA_RADIO_APPROVED", "false").lower() in ("true", "1")


def _lpi_env_default() -> bool:
    """Whether the sound-card path should carry LPI bursts by default.

    Off unless explicitly enabled, so the plain voice modem remains the default
    and nothing about the existing field behaviour changes silently. Enable with
    ``MOTOROLA_LPI_MODE=true`` (or pass ``lpi_mode=True``).
    """
    return os.environ.get("MOTOROLA_LPI_MODE", "false").lower() in ("true", "1")


class LgpioShim:
    """``RPi.GPIO``-compatible shim over ``lgpio``, for Raspberry Pi 5.

    Why this exists: ``RPi.GPIO`` reaches the pins through ``/dev/gpiomem``,
    which only describes the SoC's own GPIO block. On the Pi 5 that block moved
    behind the RP1 southbridge and ``RPi.GPIO`` fails there — the classic
    ``RuntimeError: Cannot determine SOC peripheral base address``. ``lgpio``
    talks to the kernel's GPIO character device instead, which works on every
    model, so it is the correct backend for a Pi 5 field node.

    The shim deliberately mirrors the handful of ``RPi.GPIO`` calls this module
    makes and nothing else, so the transmit path does not care which is in use.
    """

    BCM = "BCM"
    OUT = "OUT"
    LOW = 0
    HIGH = 1
    backend_name = "lgpio"

    def __init__(self, chip: int = 0):
        import lgpio  # type: ignore

        self._lgpio = lgpio
        self._h = lgpio.gpiochip_open(chip)
        self._claimed: set = set()

    def _claim(self, pin: int) -> None:
        if pin not in self._claimed:
            self._lgpio.gpio_claim_output(self._h, pin, 0)
            self._claimed.add(pin)

    def setmode(self, _mode: Any) -> None:  # API compatibility, no-op
        pass

    def setup(self, pin: int, _mode: Any, initial: int = 0) -> None:
        self._claim(pin)
        self.output(pin, initial)

    def output(self, pin: int, level: int) -> None:
        self._claim(pin)
        self._lgpio.gpio_write(self._h, pin, int(level))

    def input(self, pin: int) -> int:
        return int(self._lgpio.gpio_read(self._h, pin))

    def cleanup(self, *_a: Any) -> None:
        try:
            for pin in self._claimed:
                self._lgpio.gpio_free(self._h, pin)
            self._lgpio.gpiochip_close(self._h)
        except Exception:  # noqa: BLE001 - cleanup must never raise
            pass
        self._claimed.clear()


def _load_gpio(pin: int) -> Any:
    """Return a configured GPIO handle, or ``False`` off a Raspberry Pi.

    Tries the stock ``RPi.GPIO`` first, then falls back to :class:`LgpioShim`.
    Imported lazily so this module stays importable — and testable — on a
    developer laptop with no GPIO at all.
    """
    try:
        import RPi.GPIO as GPIO  # type: ignore

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        try:
            GPIO.backend_name = "RPi.GPIO"  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - module may forbid attribute writes
            pass
        return GPIO
    except Exception:
        pass

    try:
        shim = LgpioShim()
        shim.setmode(shim.BCM)
        shim.setup(pin, shim.OUT, initial=shim.LOW)
        return shim
    except Exception:
        return False


def gpio_backend_name(handle: Any) -> str:
    """Human name for whichever GPIO backend is in use (for the probe output)."""
    if not handle:
        return "unavailable"
    return getattr(handle, "backend_name", "RPi.GPIO")


def build_tms_pdu(radio_id_bytes: bytes, payload: bytes) -> bytes:
    """Build a minimal, self-describing TMS data PDU.

    Wire layout (little-endian):
        magic  : 2 bytes  b"TMS"
        version: 1 byte   0x01
        radio  : 1 byte   target radio short-ID (low byte)
        length : 2 bytes  payload length
        crc32  : 4 bytes  over (payload)
        payload: N bytes  <= DMR_MAX_PAYLOAD_BYTES
    """
    if len(payload) > DMR_MAX_PAYLOAD_BYTES:
        raise ValueError(f"payload exceeds DMR ceiling ({len(payload)} > {DMR_MAX_PAYLOAD_BYTES})")
    radio_lo = (radio_id_bytes[0] if radio_id_bytes else 0) & 0xFF
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    return b"TMS\x01" + struct.pack("<BH", radio_lo, len(payload)) + struct.pack("<I", crc) + payload


def parse_tms_pdu(frame: bytes) -> Dict[str, Any]:
    """Inverse of :func:`build_tms_pdu`. Raises ValueError on bad framing/CRC."""
    if len(frame) < 10 or frame[:3] != b"TMS":
        raise ValueError("not a TMS frame")
    version = frame[3]
    radio_lo, length = struct.unpack("<BH", frame[4:7])
    crc, = struct.unpack("<I", frame[7:11])
    payload = frame[11:11 + length]
    if len(payload) != length:
        raise ValueError("truncated TMS payload")
    if (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
        raise ValueError("TMS CRC mismatch")
    return {"version": version, "radio_lo": radio_lo, "length": length, "payload": payload}


@dataclass
class BridgeResult:
    success: bool
    backend: str
    dry_run: bool
    bytes_on_wire: int
    details: str
    error_code: Optional[str] = None
    delivery_id: Optional[str] = None
    latency_ms: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error_code": self.error_code,
            "delivery_id": self.delivery_id,
            "details": self.details,
            "backend": self.backend,
            "dry_run": self.dry_run,
            "bytes_on_wire": self.bytes_on_wire,
            "latency_ms": self.latency_ms,
            **self.meta,
        }


class MnisUdpBackend:
    """Send TMS data PDUs to MOTOTRBO Network Interface Service over UDP."""

    name = "mnis_udp"

    def __init__(self, host: str = DEFAULT_MNIS_HOST, port: int = DEFAULT_MNIS_PORT,
                 timeout: float = 2.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def probe(self) -> Dict[str, Any]:
        """Local socket check.

        Important: UDP ``connect()`` cannot fail for a closed port, so this
        proves only that a socket can be created and bound locally — it does
        **not** prove that an MNIS service is listening. Reporting it as
        "reachable" would let ``auto`` silently send frames into the void, so
        the field name is ``socket_ready`` and the caller must opt in
        explicitly (``MOTOROLA_BACKEND=mnis_udp``) to trust this path.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(self.timeout)
            s.connect((self.host, self.port))
            local = s.getsockname()
            return {
                "socket_ready": True,
                "reachable": False,  # not provable from a UDP connect()
                "host": self.host,
                "port": self.port,
                "local": local,
                "note": "UDP connect() does not prove a listener; set MOTOROLA_BACKEND=mnis_udp to force this path",
            }
        except OSError as e:
            return {"socket_ready": False, "reachable": False, "host": self.host,
                    "port": self.port, "error": str(e)}
        finally:
            s.close()

    def send(self, frame: bytes, dry_run: bool) -> BridgeResult:
        if dry_run:
            return BridgeResult(True, self.name, True, len(frame),
                                f"DRY-RUN: would transmit {len(frame)}B to MNIS {self.host}:{self.port}")
        t0 = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(self.timeout)
            s.sendto(frame, (self.host, self.port))
            return BridgeResult(True, self.name, False, len(frame),
                                f"Transmitted {len(frame)}B to MNIS {self.host}:{self.port}",
                                latency_ms=(time.time() - t0) * 1000.0)
        except OSError as e:
            return BridgeResult(False, self.name, False, 0,
                                f"MNIS transmit failed: {e}", error_code="MNIS_TX_ERROR")
        finally:
            s.close()


class GpioPttBackend:
    """Raspberry Pi GPIO PTT + serial/UART byte path (transparent modem).

    Uses ``RPi.GPIO`` when present and ``pyserial`` for the byte path; both are
    imported lazily so this module stays importable on a laptop for testing.
    """

    name = "gpio_ptt"

    def __init__(self, gpio_pin: int = DEFAULT_PTT_GPIO_PIN, serial_port: str = DEFAULT_SERIAL_PORT,
                 baud: int = 9600, ptt_lead_ms: int = 120):
        self.gpio_pin = gpio_pin
        self.serial_port = serial_port
        self.baud = baud
        self.ptt_lead_ms = ptt_lead_ms
        self._gpio = None

    def _load_gpio(self):
        if self._gpio is None:
            self._gpio = _load_gpio(self.gpio_pin)
        return self._gpio

    def probe(self) -> Dict[str, Any]:
        gpio = self._load_gpio()
        try:
            import serial  # noqa: F401
            serial_ok = True
        except Exception:
            serial_ok = False
        return {
            "gpio_available": bool(gpio),
            "serial_available": serial_ok,
            "gpio_pin": self.gpio_pin,
            "serial_port": self.serial_port,
        }

    def send(self, frame: bytes, dry_run: bool) -> BridgeResult:
        gpio = self._load_gpio()
        if dry_run:
            return BridgeResult(True, self.name, True, len(frame),
                                f"DRY-RUN: would key PTT on GPIO{self.gpio_pin} and write {len(frame)}B "
                                f"to {self.serial_port}")
        if not gpio:
            return BridgeResult(False, self.name, False, 0,
                                "RPi.GPIO not available on this host; GPIO PTT backend requires a Raspberry Pi",
                                error_code="GPIO_UNAVAILABLE")
        t0 = time.time()
        try:
            import serial
            gpio.output(self.gpio_pin, gpio.HIGH)      # key PTT
            time.sleep(self.ptt_lead_ms / 1000.0)       # TX settle time
            with serial.Serial(self.serial_port, self.baud, timeout=2) as ser:
                ser.write(frame)
                ser.flush()
            time.sleep(0.05)
            gpio.output(self.gpio_pin, gpio.LOW)        # release PTT
            return BridgeResult(True, self.name, False, len(frame),
                                f"Keyed PTT on GPIO{self.gpio_pin}, wrote {len(frame)}B to {self.serial_port}",
                                latency_ms=(time.time() - t0) * 1000.0)
        except Exception as e:
            try:
                gpio.output(self.gpio_pin, gpio.LOW)    # always unkey on failure
            except Exception:
                pass
            return BridgeResult(False, self.name, False, 0,
                                f"GPIO PTT transmit failed: {e}", error_code="GPIO_TX_ERROR")


class SoundCardBackend:
    """Raspberry Pi GPIO PTT + USB sound card — the transparent radio modem.

    This is the backend the field pilot uses. It knows nothing about DMR,
    TMS or MOTOTRBO: it keys a pin, plays audio, and unkeys. The radio is a
    pipe, which is exactly why it works with radios that cannot be programmed.

    Audio I/O is attempted through ``sounddevice`` (PortAudio) first and falls
    back to ALSA's ``aplay``/``arecord``, so the same code runs on a Pi with
    only ``alsa-utils`` installed.
    """

    name = "soundcard"

    def __init__(
        self,
        gpio_pin: int = DEFAULT_PTT_GPIO_PIN,
        audio_out: str = DEFAULT_AUDIO_OUT,
        audio_in: str = DEFAULT_AUDIO_IN,
        sample_rate: int = DEFAULT_AUDIO_FS,
        ptt_lead_ms: int = DEFAULT_PTT_LEAD_MS,
        ptt_tail_ms: int = DEFAULT_PTT_TAIL_MS,
        config: Optional[ModemConfig] = None,
        self_loopback: bool = False,
        lpi_mode: bool = False,
        lpi_config: Optional[Any] = None,
    ):
        self.gpio_pin = gpio_pin
        self.audio_out = audio_out
        self.audio_in = audio_in
        self.sample_rate = sample_rate
        self.ptt_lead_ms = ptt_lead_ms
        self.ptt_tail_ms = ptt_tail_ms
        self.modem = VoiceModem(config or ModemConfig(audio_fs=sample_rate))
        # LPI mode: transmit the *covert* carrier instead of the plain voice
        # modem, so that the very same radio link carries a burst whose waveform
        # and statistics are the LPI ones (see lpi_carrier.py). Both paths share
        # the AES/RS/CRC stack and the key, so a receiver in LPI mode decodes an
        # LPI burst and a receiver in plain mode decodes a plain burst -- they are
        # deliberately not cross-compatible, exactly like two different session
        # keys, because the physical layer differs.
        self.lpi_mode = lpi_mode
        self._lpi: Any = None
        if lpi_mode:
            from integration.motorola.lpi_carrier import LpiCarrier, LpiCarrierConfig

            cfg = lpi_config or LpiCarrierConfig(audio_fs=int(sample_rate))
            self._lpi = LpiCarrier(cfg)
        # Software loopback: play_audio() keeps the burst in memory and
        # receive() reads it back. This is NOT RF — it exists so the whole
        # transmit -> TMS -> demodulate -> parse chain can be proven green
        # before anything is keyed, and so CI can exercise it without a radio.
        self.self_loopback = self_loopback
        self._loopback_audio: Optional[np.ndarray] = None
        self._gpio: Any = None

    # -- capability probing ---------------------------------------------
    def _load_gpio(self) -> Any:
        if self._gpio is None:
            self._gpio = _load_gpio(self.gpio_pin)
        return self._gpio

    @staticmethod
    def _sounddevice() -> Any:
        try:
            import sounddevice as sd  # type: ignore
            return sd
        except Exception:
            return None

    def probe(self) -> Dict[str, Any]:
        sd = self._sounddevice()
        handle = self._load_gpio()
        devices: List[Any] = []
        if sd is not None:
            try:
                devices = [
                    {"index": i, "name": d.get("name"), "channels": d.get("max_output_channels")}
                    for i, d in enumerate(sd.query_devices())
                ]
            except Exception:
                devices = []
        return {
            "gpio_available": bool(handle),
            "gpio_backend": gpio_backend_name(handle),
            "gpio_pin": self.gpio_pin,
            "sounddevice_available": sd is not None,
            "aplay_available": shutil.which("aplay") is not None,
            "arecord_available": shutil.which("arecord") is not None,
            "audio_out": self.audio_out,
            "audio_in": self.audio_in,
            "sample_rate": self.sample_rate,
            "modem": {
                "symbol_rate": self.modem.cfg.symbol_rate,
                "carrier_hz": self.modem.cfg.carrier_hz,
                "sps": self.modem.cfg.sps,
                "occupied_bandwidth_hz": round(
                    self.modem.cfg.symbol_rate * (1.0 + self.modem.cfg.roll_off), 1
                ),
            },
            "devices": devices[:8],
        }

    # -- audio I/O -------------------------------------------------------
    def _play(self, audio: np.ndarray) -> str:
        sd = self._sounddevice()
        if sd is not None:
            sd.play(
                audio,
                samplerate=self.sample_rate,
                device=None if self.audio_out == "default" else self.audio_out,
                blocking=True,
            )
            return "sounddevice"
        if shutil.which("aplay") is None:
            raise RuntimeError("neither sounddevice nor aplay is available for playback")
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as fh:
            fh.write(audio.astype(np.float32).tobytes())
            path = fh.name
        try:
            subprocess.run(
                ["aplay", "-q", "-t", "raw", "-f", "FLOAT_LE", "-r", str(self.sample_rate),
                 "-c", "1", "-D", self.audio_out, path],
                check=True, timeout=120,
            )
            return "aplay"
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _record(self, duration_s: float) -> Tuple[np.ndarray, str]:
        n = max(1, int(duration_s * self.sample_rate))
        sd = self._sounddevice()
        if sd is not None:
            rec = sd.rec(n, samplerate=self.sample_rate, channels=1, dtype="float32",
                         device=None if self.audio_in == "default" else self.audio_in)
            sd.wait()
            return np.asarray(rec).reshape(-1), "sounddevice"
        if shutil.which("arecord") is None:
            raise RuntimeError("neither sounddevice nor arecord is available for capture")
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as fh:
            path = fh.name
        try:
            subprocess.run(
                ["arecord", "-q", "-t", "raw", "-f", "FLOAT_LE", "-r", str(self.sample_rate),
                 "-c", "1", "-D", self.audio_in, "-d", str(int(np.ceil(duration_s))), path],
                check=True, timeout=120,
            )
            with open(path, "rb") as fh:
                raw = fh.read()
            return np.frombuffer(raw, dtype=np.float32).copy(), "arecord"
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    # -- transmit --------------------------------------------------------
    def _key(self, gpio: Any, high: bool) -> None:
        if gpio:
            gpio.output(self.gpio_pin, gpio.HIGH if high else gpio.LOW)

    def play_audio(self, audio: np.ndarray, dry_run: bool, label: str = "burst") -> BridgeResult:
        """Key PTT, play ``audio``, unkey — the whole radio transmission."""
        duration = audio.size / float(self.sample_rate)

        # Software loopback sits *before* the safety gate because it is not a
        # transmission at all — nothing leaves the process. It still reports
        # dry_run=True so no caller can mistake it for RF.
        if self.self_loopback:
            self._loopback_audio = np.asarray(audio, dtype=np.float32).copy()
            return BridgeResult(
                True, self.name, True, int(audio.size),
                f"SOFTWARE LOOPBACK: captured {duration:.3f}s of {label} audio in memory; no RF emitted",
                meta={"sink": "software_loopback", "audio_seconds": round(duration, 4),
                      "label": label, "note": "software loopback — not a radio transmission"},
            )

        if dry_run:
            return BridgeResult(
                True, self.name, True, int(audio.size),
                f"DRY-RUN: would key GPIO{self.gpio_pin}, play {duration:.3f}s of {label} audio "
                f"({self.modem.cfg.symbol_rate:.0f} Bd on {self.modem.cfg.carrier_hz:.0f} Hz) "
                f"to '{self.audio_out}', then unkey",
                meta={"audio_seconds": round(duration, 4), "label": label},
            )
        gpio = self._load_gpio()
        if self.self_loopback:
            self._loopback_audio = np.asarray(audio, dtype=np.float32).copy()
            return BridgeResult(
                True, self.name, False, int(audio.size),
                f"SOFTWARE LOOPBACK: captured {duration:.3f}s of {label} audio in memory (nothing radiated)",
                latency_ms=0.0,
                meta={"sink": "software_loopback", "audio_seconds": round(duration, 4), "label": label},
            )
        if not gpio:
            return BridgeResult(False, self.name, False, 0,
                                "RPi.GPIO not available on this host; sound-card backend requires a Raspberry Pi",
                                error_code="GPIO_UNAVAILABLE")
        t0 = time.time()
        try:
            self._key(gpio, True)
            time.sleep(self.ptt_lead_ms / 1000.0)     # let the PA and the far-end squelch open
            sink = self._play(audio)
            time.sleep(self.ptt_tail_ms / 1000.0)     # let the last symbol out before unkeying
            self._key(gpio, False)
            return BridgeResult(
                True, self.name, False, int(audio.size),
                f"Keyed PTT on GPIO{self.gpio_pin}, played {duration:.3f}s via {sink}, unkeyed",
                latency_ms=(time.time() - t0) * 1000.0,
                meta={"sink": sink, "audio_seconds": round(duration, 4), "label": label},
            )
        except Exception as e:  # noqa: BLE001
            self._key(gpio, False)                   # never leave PTT held
            return BridgeResult(False, self.name, False, 0,
                                f"Sound-card transmit failed: {e}", error_code="AUDIO_TX_ERROR")

    def send(self, frame: bytes, dry_run: bool) -> BridgeResult:
        """Interface compatibility: modulate the framed bytes and transmit."""
        try:
            if self._lpi is not None:
                audio = self._lpi.modulate(frame, seed=self._lpi_seed(frame))
            else:
                audio = self.modem.modulate(frame)
        except Exception as e:  # noqa: BLE001
            return BridgeResult(False, self.name, dry_run, 0, f"Modulation failed: {e}",
                                error_code="MODEM_ENCODE_ERROR")
        res = self.play_audio(audio, dry_run, label="LPI burst" if self._lpi else "data burst")
        if res.success:
            # ``bytes_on_wire`` must describe the DMR frame that goes over the air,
            # not the audio buffer that carries it. ``play_audio`` reports the
            # sample count in that slot because it has no frame to talk about;
            # here we do, so correct it and keep the sample count alongside under
            # its own name. (Measured before this fix: a 21-byte payload reported
            # 159744 "bytes on wire", which was the audio sample count.)
            res.bytes_on_wire = len(frame)
            res.meta["modulated_bytes"] = len(frame)
            res.meta["audio_samples"] = int(audio.size)
            if self._lpi is not None:
                res.meta["lpi"] = True
                res.meta["air_time_s"] = round(
                    self._lpi.burst_seconds(len(frame)), 4)
            else:
                res.meta["air_time_s"] = round(self.modem.burst_seconds(len(frame)), 4)
        return res

    @staticmethod
    def _lpi_seed(frame: bytes) -> int:
        """Deterministic per-frame seed so a capture stays reproducible.

        The seed only drives the masking dither; it is not a secret and is
        derived from the payload so the same message always renders the same
        burst, which is what the EW battery needs to be repeatable.
        """
        import hashlib

        return int.from_bytes(hashlib.sha256(frame).digest()[:8], "big")

    def receive(self, duration_s: float, save_wav: Optional[str] = None) -> Tuple[Optional[bytes], Dict[str, Any]]:
        """Record from the radio's speaker and demodulate. Returns (payload, meta)."""
        if self.self_loopback:
            audio = self._loopback_audio
            source = "software_loopback"
            if audio is None:
                return None, {"ok": False, "source": source,
                              "error": "no burst has been transmitted on this loopback yet",
                              "error_code": "LOOPBACK_EMPTY"}
        else:
            try:
                audio, source = self._record(duration_s)
            except Exception as e:  # noqa: BLE001
                return None, {"ok": False, "error": str(e), "error_code": "AUDIO_RX_ERROR"}

        if save_wav:
            try:
                write_wav(save_wav, audio, self.sample_rate)
            except Exception:  # noqa: BLE001 - a failed dump must not lose the decode
                pass

        if self._lpi is not None:
            res = self._lpi.demodulate(audio)
            return res.payload, {
                "ok": res.ok,
                "source": source,
                "lpi": True,
                "pilot_score": res.meta.get("pilot_score"),
                "detail": res.detail,
                "captured_seconds": round(audio.size / float(self.sample_rate), 4),
                "levels": audio_levels(audio),
                **res.meta,
            }

        decoded = self.modem.demodulate(audio)
        return decoded.payload, {
            "ok": decoded.ok,
            "source": source,
            "sync_score": round(decoded.sync_score, 3),
            "phase_offset": decoded.phase_offset,
            "detail": decoded.detail,
            "captured_seconds": round(audio.size / float(self.sample_rate), 4),
            # Audio levels, because "nothing decoded" is nearly always a wiring
            # or gain problem and these numbers say which one.
            "levels": audio_levels(audio),
            **{k: v for k, v in decoded.meta.items() if k != "_rank"},
        }


class MotorolaHardwareBridge:
    """Front door for physical Motorola dispatch.

    ``backend`` selects the transport: ``"mnis_udp"``, ``"gpio_ptt"``,
    ``"soundcard"``, ``"sdr_usrp"``, or ``"auto"``. ``auto`` resolves to the
    transparent sound-card modem — never MNIS, because a UDP ``connect()`` cannot
    prove MNIS is listening (see the module docstring).

    ``sdr_usrp`` carries the **same** Motorola LPI burst over a USRP instead of
    the radio's microphone input: one waveform, two transports. It is never
    chosen by ``auto`` because radiated power and licensing are the operator's
    decision, not a default.
    """

    def __init__(self, backend: str = "auto", **kwargs: Any):
        self._requested = backend or os.environ.get("MOTOROLA_BACKEND", "auto")
        self._kwargs = kwargs
        self._mnis = kwargs.get("mnis") or MnisUdpBackend(
            host=kwargs.get("host", DEFAULT_MNIS_HOST),
            port=kwargs.get("port", DEFAULT_MNIS_PORT),
        )
        self._gpio = kwargs.get("gpio") or GpioPttBackend(
            gpio_pin=kwargs.get("gpio_pin", DEFAULT_PTT_GPIO_PIN),
            serial_port=kwargs.get("serial_port", DEFAULT_SERIAL_PORT),
        )
        self._sound = kwargs.get("sound") or SoundCardBackend(
            gpio_pin=kwargs.get("gpio_pin", DEFAULT_PTT_GPIO_PIN),
            audio_out=kwargs.get("audio_out", DEFAULT_AUDIO_OUT),
            audio_in=kwargs.get("audio_in", DEFAULT_AUDIO_IN),
            sample_rate=kwargs.get("sample_rate", DEFAULT_AUDIO_FS),
            lpi_mode=bool(kwargs.get("lpi_mode", _lpi_env_default())),
            lpi_config=kwargs.get("lpi_config"),
            self_loopback=bool(kwargs.get("self_loopback", False)),
        )
        self._sdr = kwargs.get("sdr")

    def approved(self) -> bool:
        return _is_approved()

    def select_backend(self) -> str:
        if self._requested in ("mnis_udp", "gpio_ptt", "soundcard", "sdr_usrp"):
            return self._requested
        # "auto": the sound-card modem. A UDP connect() cannot tell us whether
        # MOTOTRBO Network Interface Service is actually listening, so choosing
        # it automatically risks transmitting into the void and reporting
        # success. The sound-card path always either works or fails loudly, so
        # it is the honest default. Force MNIS explicitly when you know it is up.
        # SDR is excluded from auto for the same reason it is opt-in: radiating
        # through a USRP is a licensing and power decision, not a fallback.
        return "soundcard"

    def _sdr_backend(self):
        """Build the SDR transport once, reusing the sound card's LPI carrier."""
        if self._sdr is None:
            from integration.motorola.sdr_backend import SdrBackend

            self._sdr = SdrBackend(
                addr=self._kwargs.get("sdr_addr", ""),
                rate=float(self._kwargs.get("sdr_rate", 245_760.0)),
                freq=float(self._kwargs.get("sdr_freq", 2.484e9)),
                gain=float(self._kwargs.get("sdr_gain", 0.0)),
                ant=self._kwargs.get("sdr_ant", ""),
                lpi=self._sound._lpi,
                seed_fn=SoundCardBackend._lpi_seed,
            )
        return self._sdr

    def _backend(self, name: Optional[str] = None) -> Any:
        name = name or self.select_backend()
        if name == "mnis_udp":
            return self._mnis
        if name == "gpio_ptt":
            return self._gpio
        if name == "sdr_usrp":
            return self._sdr_backend()
        return self._sound

    def probe(self) -> Dict[str, Any]:
        return {
            "approved": self.approved(),
            "requested_backend": self._requested,
            "selected_backend": self.select_backend(),
            "mnis": self._mnis.probe(),
            "gpio": self._gpio.probe(),
            "soundcard": self._sound.probe(),
            "sdr": self._sdr_backend().probe(),
            "lpi_mode": bool(getattr(self._sound, "lpi_mode", False)),
            "dmr_max_payload_bytes": DMR_MAX_PAYLOAD_BYTES,
        }

    def transmit(self, recipient_endpoint_id: str, payload: bytes) -> Dict[str, Any]:
        if len(payload) > DMR_MAX_PAYLOAD_BYTES:
            return BridgeResult(False, self.select_backend(), not self.approved(), 0,
                                f"payload {len(payload)}B exceeds DMR {DMR_MAX_PAYLOAD_BYTES}B ceiling",
                                error_code="PAYLOAD_TOO_LARGE").as_dict()

        radio_id = recipient_endpoint_id.encode("utf-8")
        frame = build_tms_pdu(radio_id, payload)
        dry_run = not self.approved()
        backend_name = self.select_backend()
        backend = self._backend(backend_name)
        res = backend.send(frame, dry_run)
        if res.success:
            res.delivery_id = f"mot-{backend_name}-{os.urandom(4).hex()}"
        return res.as_dict()

    # -- voice path (the field-pilot transport) --------------------------
    def transmit_voice(self, recipient_endpoint_id: str, payload: bytes,
                       chunk: bool = True) -> Dict[str, Any]:
        """Send a message over the sound-card voice path.

        Payloads are spread with the TMS header so the receiver sees the same
        framing as the data path, then handed to the modem. The DMR 280 B
        ceiling still applies because the receiving stack will eventually hand
        these to the same reconciliation logic.
        """
        if len(payload) > DMR_MAX_PAYLOAD_BYTES:
            return BridgeResult(False, "soundcard", not self.approved(), 0,
                                f"payload {len(payload)}B exceeds DMR {DMR_MAX_PAYLOAD_BYTES}B ceiling",
                                error_code="PAYLOAD_TOO_LARGE").as_dict()
        frame = build_tms_pdu(recipient_endpoint_id.encode("utf-8"), payload)
        dry_run = not self.approved()
        res = self._sound.send(frame, dry_run)
        if res.success:
            res.delivery_id = f"mot-voice-{os.urandom(4).hex()}"
            res.meta["transport"] = "soundcard_voice"
            res.meta["dmr_frame_bytes"] = len(frame)
            # Same correction as ``send``: the frame is what goes on the air.
            res.meta["audio_samples"] = int(res.bytes_on_wire)
            res.bytes_on_wire = len(frame)
        return res.as_dict()

    def receive_voice(self, duration_s: float, save_wav: Optional[str] = None) -> Dict[str, Any]:
        """Record the far-end radio and demodulate a message. RX needs no gate."""
        payload, meta = self._sound.receive(duration_s, save_wav=save_wav)
        out: Dict[str, Any] = dict(meta)
        out["transport"] = "soundcard_voice"
        if payload is None:
            out["payload"] = None
            return out
        try:
            pdu = parse_tms_pdu(payload)
            body = pdu["payload"]
            out["tms_crc_ok"] = True
            out["tms_radio_lo"] = pdu["radio_lo"]
        except ValueError as e:
            # A raw burst with no TMS wrapper is still a successful demod, so
            # report it rather than hiding it.
            body = payload
            out["tms_crc_ok"] = False
            out["tms_error"] = str(e)

        # Text is the normal case, but never destroy binary: keep the exact
        # bytes alongside the decoded text so a caller can always recover them.
        out["payload_bytes"] = len(body)
        out["payload_hex"] = body.hex()
        try:
            out["payload"] = body.decode("utf-8")
            out["payload_is_utf8"] = True
        except UnicodeDecodeError:
            out["payload"] = body.decode("utf-8", errors="replace")
            out["payload_is_utf8"] = False
        return out

    def self_test(self, **kwargs: Any) -> Dict[str, Any]:
        """Modem loopback through a simulated channel. No RF, no hardware."""
        from integration.motorola.voice_modem import loopback_selftest
        report = loopback_selftest(**kwargs)
        report["backend"] = "soundcard"
        report["approved"] = self.approved()
        report["dry_run"] = not self.approved()
        return report
