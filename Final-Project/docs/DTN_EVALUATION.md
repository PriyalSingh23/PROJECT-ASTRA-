# DELAY-TOLERANT NETWORKING (DTN) EVALUATION & BPv7 (RFC 9171) ASSESSMENT

**Topic**: Delay-Tolerant Networking & IETF Bundle Protocol Version 7 Evaluation  
**Standard Evaluated**: RFC 9171 (Bundle Protocol Version 7)  
**System**: SHADOWLINK Resilient Communications Platform  
**Status**: Architectural Decision Record (ADR)  

---

## 1. Context & Operational Need

Field emergency responders, remote industrial sites, and tactical units operate across "challenged networks" characterized by:
- Intermittent connectivity and frequent link outages.
- High round-trip latency (satellite, HF radio, acoustic links).
- Absence of continuous end-to-end routing paths.
- Asymmetric bandwidth and packet loss.

To address these conditions, SHADOWLINK implements store-and-forward queueing. This report evaluates whether standardizing directly on **IETF Bundle Protocol Version 7 (BPv7, RFC 9171)** is justified for the current release.

---

## 2. Comparative Analysis: SHADOWLINK vs IETF BPv7

| Dimension | SHADOWLINK Store-and-Forward Engine | IETF BPv7 (RFC 9171) |
|:---|:---|:---|
| **Primary Serialization** | JSON & SQLite relational records with WAL mode | Concise Binary Object Representation (CBOR) |
| **Node Naming / Addressing** | Logical endpoint IDs (`endpoint-a`, `endpoint-b`) | URI-based Endpoint Identifiers (`dtn://node-a/`, `ipn:1.2`) |
| **Routing / Forwarding** | Hop-by-hop local broker & relay node registry | Contact Graph Routing (CGR), PRoPHET, or Epidemic routing |
| **Custody & Delivery Semantics** | At-least-once delivery with receiver-signed receipts | Administrative records, Bundle status reports, optional custody transfer |
| **Storage Engine** | Embedded SQLite with indexing & ACID transactions | Custom block storage / BerkeleyDB / RocksDB bundle store |
| **Resource Footprint** | Extremely lightweight (~15 MB RAM, Python 3.12 / SQLite) | Moderate to heavy (requires CBOR parser, canonical block validator) |
| **Hardware Dependencies** | Zero (runs on Mac, Raspberry Pi, Android, Linux edge) | Zero, but requires standardized DTN daemon (e.g., ION, μPCN) |

---

## 3. Engineering Assessment & Trade-Offs

### 3.1. Advantages of BPv7:
1. **Inter-Agency Interoperability**: NASA, ESA, military networks, and civilian emergency response coalitions recognize BPv7 for cross-domain gateway routing.
2. **Canonical Security Block (BPSec / RFC 9172)**: Standardized hop-by-hop authentication and payload integrity blocks.

### 3.2. Practical Disadvantages for Local Field Pilot:
1. **Implementation Overhead**: Full RFC 9171 compliance entails implementing primary bundle blocks, canonical block ordering, CRC validation, CBOR indefinite-length encodings, and administrative record generation.
2. **Debugging & Operator Accessibility**: Relational SQLite allows operators and incident commanders to inspect message queues, timeline events, and delivery attempts via standard SQL queries and simple REST endpoints. CBOR binary bundles require specialized dissection tooling.
3. **No Added Benefit for Two-Node LAN**: In a dual-endpoint local pilot with a central gateway or direct peer links, BPv7 provides no functional benefit over SHADOWLINK's persistent SQLite outbox and signed receipt mechanism.

---

## 4. Architectural Decision: The Phased BPv7 Bridge

> [!NOTE]
> **Decision**: Retain the existing SHADOWLINK SQLite WAL store-and-forward engine for Milestone 1 & 2 field pilot deployments. Implement a **BPv7 Ingress/Egress Convergence Layer Adapter** in Milestone 3 for external DTN interoperability.

### The BPv7 Mapping Specification:
When inter-operating with a BPv7 network:
1. `message_id` maps to the Bundle's Creation Timestamp + Sequence Number.
2. `sender_endpoint_id` maps to the Source EID (`dtn://shadowlink/<sender_id>`).
3. `recipient_endpoint_id` maps to Destination EID (`dtn://shadowlink/<recipient_id>`).
4. `expires_at` maps to the Bundle Lifetime in milliseconds.
5. `priority` maps to BPv7 Quality of Service (QoS) flags (Bulk, Normal, Expedited).
6. Payload is carried verbatim inside the BPv7 Payload Block.
