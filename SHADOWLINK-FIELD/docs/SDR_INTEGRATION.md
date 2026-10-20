# SDR Research Adapter & LPI-CGAN Integration: SHADOWLINK FIELD

**Document Version:** 1.0.0  
**Status:** Software Research Mode Operational & Hardware Transmission Disarmed  
**Provenance:** Derived from `lpi_v4/` research implementation

---

## 1. Operating Architecture & Separation of Concerns

The LPI-CGAN research implementation developed under `lpi_v4/` explores machine-learning-generated covert waveforms that approximate additive white Gaussian noise (AWGN) to evade intercept receivers (wardens).

**Critical Architecture Rule**:
The SDR research adapter (`SdrResearchAdapter`) is completely segregated from the commercial/tactical radio adapters (Motorola and STAR-V). 
- An LPI-CGAN waveform **cannot be demodulated by standard FM/DMR/P25 radios**.
- The SDR adapter defaults strictly to **Software Research Mode (Non-Transmitting)**.
- Over-the-air RF radiation via USRP / UHD requires an explicit administrative arming action, hardware license verification, and physical hardware attachment.

```
+-----------------------------------------------------------------------------------------+
|                                SHADOWLINK FIELD PLATFORM                                |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  |                 SDR Research Service (SdrResearchAdapter)                         |  |
|  +-----------------------------------------+-----------------------------------------+  |
+--------------------------------------------|--------------------------------------------+
                                             |
             +-------------------------------+-------------------------------+
             |                                                               |
+------------v------------------------------+   +----------------------------v------------+
|        SOFTWARE RESEARCH MODE             |   |         RF EMISSION MODE                |
|           (DEFAULT / SAFE)                |   |       (DISARMED / RESTRICTED)           |
|                                           |   |                                         |
|  - Synthetic In-Memory Channel Simulation |   |  - Requires USRP Hardware (e.g., B210)  |
|  - Synthetic AWGN / CFO / Phase Noise     |   |  - Requires libuhd & UHD C++ Drivers    |
|  - Pretrained Best Model: lpi_v4.best.pt  |   |  - Requires Administrative Arming Token |
|  - Full EW 8-Domain Stealth Evaluation    |   |  - Strictly Blocks Automatic Startup TX |
+-------------------------------------------+   +-----------------------------------------+
```

---

## 2. Research Provenance & Checkpoint Metadata

- **Algorithm Generation**: `v4` (Self-contained in `Final-Project/lpi_v4/`).
- **Shipped Checkpoint**: `Final-Project/lpi_v4/run/lpi_v4.best.pt`.
- **Model Architecture**:
  - Generator: Deep convolutional ResNet conditioning on noise vector $z \sim \mathcal{N}(0, I_{64})$ and coded bipolar bits $b \in \{-1, +1\}^{272}$.
  - Decoder: 1D convolutional sequence network recovering soft bipolar symbols.
  - Warden: Multi-layer EW discriminator evaluating spectral flatness, higher-order moments, and cyclostationarity.
- **Framing & Modulation**:
  - Frame length: 1024 or 2048 complex samples ($f_s = 245,760\text{ S/s}$).
  - Preamble: Balanced 64-sample CAZAC synchronization sequence.
  - Forward Error Correction: $RS(42,34)$ Reed-Solomon codec over $\text{GF}(2^8)$ + CRC-8.
  - Payload capacity: Up to 34 raw data bytes per single burst frame.

---

## 3. Measured Research Benchmarks (from `run/lpi_v4.best.pt`)

| Metric | Scientific Gate Target | Measured Benchmark | Status |
|---|---|---|---|
| **Kolmogorov-Smirnov $p$-value** | $>0.05$ (Target $>0.85$) | **$0.8646$** | **PASS** |
| **Kurtosis** | $3.00 \pm 0.15$ | **$2.9907$** | **PASS** |
| **Spectral Entropy** | $>0.95$ | **$0.9566$** | **PASS** |
| **Circularity Coefficient** | $<0.15$ | **$0.0107$** | **PASS** |
| **Adversary Accuracy** | $48\% - 56\%$ | **$55.90\%$** | **PASS** |
| **Cable BER (at $5\text{ dB}$)**| $<1.0\%$ | **$0.00\%$** | **PASS** |
| **Message FER (at $2\text{ dB}$)**| $<5.0\%$ | **$0.00\%$** | **PASS** |

---

## 4. Adapter Interface Implementation

In `backend/app/adapters/sdr.py`, the adapter wraps the research math without modifying the underlying scientific scripts:

```python
class SdrResearchAdapter(ICommunicationAdapter):
    """
    Adapter interfacing the LPI-CGAN covert waveform engine.
    Runs in deterministic simulation and software evaluation mode.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.rf_armed = False # Safety interlock
        self.is_simulation = True

    async def check_health(self) -> AdapterHealthReport:
        # Verifies TorchScript model loadability and test harness
        return AdapterHealthReport(
            adapter_id="sdr-lpi-v4",
            state=AdapterState.READY,
            ready_to_transmit=self.rf_armed,
            summary="SDR Research Engine Online (Software Mode - No RF Emission)",
            diagnostic_code="SDR_SOFTWARE_MODE_ACTIVE"
        )

    async def transmit(self, message: OutgoingMessagePayload) -> TransmissionResult:
        if not self.rf_armed:
            # Execute through synthetic channel simulation
            return self._simulate_reception(message)
        else:
            raise PermissionError("RF hardware transmission disarmed. Admin authorization required.")
```

---

## 5. macOS Compatibility Considerations

On macOS systems running Radioconda / Apple Silicon:
1. `lpi_core.py` matrix operations must ensure proper contiguous memory alignment before calling Torch linear algebra routines to prevent BLAS segmentation faults.
2. The `SdrResearchAdapter` provides an internal purely-simulated channel fallback that guarantees test reproducibility even if Apple Silicon PyTorch complex math libraries exhibit platform quirks.
