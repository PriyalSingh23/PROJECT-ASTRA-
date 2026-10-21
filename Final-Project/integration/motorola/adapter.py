import os
from typing import Dict, List, Any
from integration.base import (
    BaseTransportAdapter,
    TransportReadiness,
    TransportConnectionState,
    utcnow_iso,
)
from integration.motorola.hardware_bridge import MotorolaHardwareBridge


class MotorolaMOTOTRBOAdapter(BaseTransportAdapter):
    """Motorola MOTOTRBO adapter — the PRIMARY transport for PROJECT ASTRA.

    This is NOT an optional secondary adapter. Motorola is the actual
    application of the project. Every message sent through this adapter
    generates a real LPI-modulated audio burst via the ``LpiCarrier``
    pipeline, whether on a developer laptop (software loopback) or on a
    Raspberry Pi 5 (GPIO PTT + USB sound card → radio).

    The LPI carrier ensures that when the audio is transmitted over a
    Motorola radio and intercepted, the waveform is statistically
    indistinguishable from noise across 6+ of the 8 EW battery domains.

    Architecture:
      * ``lpi_mode=True`` is the default — every transmission goes through
        the keyed codebook spread + dither + Zadoff-Chu pilot pipeline.
      * On macOS/Linux dev machines: ``self_loopback=True`` — real LPI audio
        is generated and captured in memory but nothing is radiated.
      * On Raspberry Pi 5 with ``MOTOROLA_RADIO_APPROVED=true``: the bridge
        keys GPIO17 PTT and plays the burst through the USB sound card into
        the Motorola radio's mic input.
      * Every burst's audio samples are pushed to the shared
        ``LpiWaveformBuffer`` so the Web Console's Spectrum & Waveform panels
        display actual Motorola LPI data.
    """

    def __init__(self, transport_id: str = "motorola-mototrbo-01", radio_model: str = "MOTOTRBO XPR 7550e / DP4801e"):
        super().__init__(transport_id, display_name=f"Motorola MOTOTRBO ({radio_model})")
        self.radio_model = radio_model
        self._is_hardware_authorized = os.environ.get("MOTOROLA_RADIO_APPROVED", "false").lower() in ("true", "1")

        # LPI mode is the default — this is the whole point of the project.
        # On dev machines, self_loopback=True captures real LPI audio in memory.
        # On Pi 5 with MOTOROLA_RADIO_APPROVED=true, self_loopback is off and
        # the bridge plays through the USB sound card.
        is_loopback = not self._is_hardware_authorized
        self._bridge = MotorolaHardwareBridge(
            lpi_mode=True,
            self_loopback=is_loopback,
        )
        self._connection_state = TransportConnectionState.STANDBY

    @property
    def transport_type(self) -> str:
        return "MOTOROLA_MOTOTRBO"

    @property
    def supported_operations(self) -> List[str]:
        return [
            "TMS_TEXT_MESSAGE",
            "LOCATION_REPORT",
            "TELEMETRY_IO",
            "DEVICE_DISCOVERY_ARS",
            "RAW_DATA_BURST",
            "LPI_COVERT_BURST",
        ]

    @property
    def readiness(self) -> TransportReadiness:
        if self._is_hardware_authorized:
            return TransportReadiness.READY
        return TransportReadiness.SIMULATION_ONLY

    @property
    def connection_state(self) -> TransportConnectionState:
        return self._connection_state

    def send(self, recipient_endpoint_id: str, payload_bytes: bytes, message_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches message via LPI-modulated Motorola carrier.

        Every call generates a real LPI audio burst. On dev machines this
        burst lives in the software loopback buffer; on Pi 5 it is radiated
        through the radio. Either way the burst's audio samples are pushed
        to the shared ``LpiWaveformBuffer`` for live UI display.
        """
        payload_len = len(payload_bytes)
        if payload_len > 280:
            err = f"Payload size {payload_len} bytes exceeds Motorola TMS DMR packet size limit of 280 bytes"
            self.record_error("PAYLOAD_TOO_LARGE", err)
            return {
                "success": False,
                "error_code": "PAYLOAD_TOO_LARGE",
                "details": err,
                "delivery_id": None,
            }

        # Route through the bridge — which now always runs LPI carrier mode.
        # In loopback mode the bridge generates real audio samples without
        # radiating. In hardware mode it keys PTT and plays through the
        # USB sound card.
        dispatch = self._bridge.transmit(recipient_endpoint_id, payload_bytes)
        self.last_operation_at = utcnow_iso()

        if dispatch.get("success"):
            self._connection_state = TransportConnectionState.ONLINE

            # Push the LPI audio to the shared waveform buffer for live UI display.
            self._capture_lpi_burst(
                dispatch,
                message_id=message_metadata.get("message_id"),
                sender=message_metadata.get("sender_endpoint_id"),
                recipient=recipient_endpoint_id,
            )
        else:
            self.record_error(
                dispatch.get("error_code") or "MOTOROLA_TX_FAILED",
                dispatch.get("details", ""),
            )

        # Delivery id and details must say what actually happened. Without
        # MOTOROLA_RADIO_APPROVED the burst is generated and captured in memory
        # but nothing is radiated, so the id keeps the ``mot-tms-`` prefix of the
        # TMS service and the details say plainly that the dispatch was
        # simulated. With approval the bridge reports the real backend it used
        # (e.g. ``mot-soundcard-``), which is the honest label for an RF path.
        # The LPI burst is generated either way -- that is the point of the
        # project, not an option.
        if dispatch.get("success") and not self._is_hardware_authorized:
            delivery_id = f"mot-tms-{os.urandom(4).hex()}"
            details = (
                f"Dispatched via Motorola TMS adapter "
                f"(Model: {self.radio_model}, simulated): "
                f"{dispatch.get('details')}"
            )
        else:
            delivery_id = dispatch.get("delivery_id")
            details = dispatch.get("details")

        return {
            "success": bool(dispatch.get("success")),
            "delivery_id": delivery_id,
            "error_code": dispatch.get("error_code"),
            "details": details,
            "radio_id": recipient_endpoint_id,
            "backend": dispatch.get("backend"),
            "bytes_on_wire": dispatch.get("bytes_on_wire"),
            "lpi_mode": True,
            "lpi_meta": {
                "waveform_source": "keyed_spread_plus_dither_at_audio_scale",
                "carrier_hz": 1650.0,
                "occupied_hz": 2700.0,
                "symbol_rate": 2000.0,
            },
        }

    def _capture_lpi_burst(
        self,
        dispatch: Dict[str, Any],
        message_id: str = None,
        sender: str = None,
        recipient: str = None,
    ) -> None:
        """Capture the LPI audio burst into the shared waveform buffer.

        The SoundCardBackend in loopback mode stores the audio in
        ``_loopback_audio``. We grab it from there.
        """
        try:
            from integration.motorola.lpi_waveform_buffer import lpi_waveform_buffer

            # Get the audio from the sound card backend's loopback buffer
            sound_backend = self._bridge._sound
            audio = getattr(sound_backend, '_loopback_audio', None)

            if audio is not None and audio.size > 0:
                lpi_waveform_buffer.push_audio(
                    audio=audio,
                    sample_rate=sound_backend.sample_rate,
                    message_id=message_id,
                    sender=sender,
                    recipient=recipient,
                    lpi_meta={
                        "delivery_id": dispatch.get("delivery_id"),
                        "backend": dispatch.get("backend"),
                        "lpi": True,
                        "dry_run": dispatch.get("dry_run", False),
                    },
                )
        except Exception:
            pass  # Never let buffer capture failure block message delivery

    def bridge_probe(self) -> Dict[str, Any]:
        """Non-transmitting hardware reachability report (MNIS / GPIO)."""
        return self._bridge.probe()

    def health_check(self) -> Dict[str, Any]:
        self.last_health_check_at = utcnow_iso()
        probe = self._bridge.probe()
        return {
            "transport_id": self.transport_id,
            "radio_model": self.radio_model,
            "hardware_authorized": self._is_hardware_authorized,
            "readiness": self.readiness.value,
            "connection_state": self.connection_state.value,
            "supported_operations": self.supported_operations,
            "max_payload_bytes": 280,
            "last_operation_at": self.last_operation_at,
            "lpi_mode": True,
            "lpi_carrier": {
                "waveform_source": "keyed_spread_plus_dither_at_audio_scale",
                "carrier_hz": 1650.0,
                "occupied_hz": 2700.0,
                "symbol_rate": 2000.0,
                "dither_eps": 0.10,
            },
            "bridge": probe,
        }
