"""Self-contained Pure-Python NIST FIPS 203 ML-KEM-768 Core Engine.

Conforms strictly to NIST FIPS 203 (Module-Lattice-Based Key-Encapsulation
Mechanism Standard, August 2024) for ML-KEM-768.

Zero C-compiler dependencies, 100% pure Python standard library:
- Hash functions: hashlib.sha3_256, hashlib.sha3_512, hashlib.shake_128, hashlib.shake_256
- Constant-time secret comparison: secrets.compare_digest
- Random entropy: secrets.token_bytes
"""

import hashlib
import secrets
from typing import List, Tuple

# ==============================================================================
# ML-KEM-768 Parameters (NIST FIPS 203 Table 2)
# ==============================================================================
MLKEM_K = 3            # Module rank
MLKEM_Q = 3329         # Modulus (q = 13 * 256 + 1)
MLKEM_N = 256          # Ring dimension (degree of polynomials)
MLKEM_ETA1 = 2         # CBD parameter for keygen & encryption
MLKEM_ETA2 = 2         # CBD parameter for encryption noise
MLKEM_DU = 10          # Compression bits for vector u
MLKEM_DV = 4           # Compression bits for polynomial v

MLKEM_EK_BYTES = 1184  # Encapsulation key: 384 * k + 32 = 1184 bytes
MLKEM_DK_BYTES = 2400  # Decapsulation key: 384 * k + 1184 + 32 + 32 = 2400 bytes
MLKEM_CT_BYTES = 1088  # Ciphertext: 320 * k + 128 = 1088 bytes
MLKEM_SS_BYTES = 32    # Shared secret: 32 bytes (256 bits)


def _bit_rev_7(n: int) -> int:
    """Computes the 7-bit reversal of integer n."""
    r = 0
    for _ in range(7):
        r = (r << 1) | (n & 1)
        n >>= 1
    return r


# Precomputed bit-reversed powers of root of unity zeta = 17 mod 3329
# 17^128 = -1 = 3328 mod 3329, 17^256 = 1 mod 3329
ZETAS: List[int] = [pow(17, _bit_rev_7(i), MLKEM_Q) for i in range(128)]

# Precomputed gamma values for base multiplication in NTT domain
# gamma_i = 17^(2 * BitRev_7(i) + 1) mod 3329
GAMMAS: List[int] = [pow(17, 2 * _bit_rev_7(i) + 1, MLKEM_Q) for i in range(128)]

# 128^-1 mod 3329 = 3303 (scaling factor for inverse NTT)
INTT_SCALE = 3303


# ==============================================================================
# Number Theoretic Transform (NTT) & Ring Arithmetic
# ==============================================================================
def ntt(f: List[int]) -> List[int]:
    """Forward Cooley-Tukey NTT transforming polynomial f mod (X^256 + 1).

    Transforms f in Z_q[X]/(X^256 + 1) into an array of 128 degree-1 elements.
    """
    a = list(f)
    i = 1
    length = 128
    while length >= 2:
        start = 0
        while start < 256:
            zeta = ZETAS[i]
            i += 1
            for j in range(start, start + length):
                t = (zeta * a[j + length]) % MLKEM_Q
                a[j + length] = (a[j] - t) % MLKEM_Q
                a[j] = (a[j] + t) % MLKEM_Q
            start += 2 * length
        length //= 2
    return a


def intt(a_in: List[int]) -> List[int]:
    """Inverse Gentleman-Sande NTT transforming frequency coefficients back."""
    a = list(a_in)
    i = 127
    length = 2
    while length <= 128:
        start = 0
        while start < 256:
            zeta = ZETAS[i]
            i -= 1
            for j in range(start, start + length):
                t = a[j]
                a[j] = (t + a[j + length]) % MLKEM_Q
                a[j + length] = (zeta * (a[j + length] - t)) % MLKEM_Q
            start += 2 * length
        length *= 2
    for j in range(256):
        a[j] = (a[j] * INTT_SCALE) % MLKEM_Q
    return a


def base_case_multiply(a0: int, a1: int, b0: int, b1: int, gamma: int) -> Tuple[int, int]:
    """Multiplies two degree-1 polynomials mod (X^2 - gamma) mod q."""
    c0 = (a0 * b0 + a1 * b1 * gamma) % MLKEM_Q
    c1 = (a0 * b1 + a1 * b0) % MLKEM_Q
    return c0, c1


def multiply_ntts(a_hat: List[int], b_hat: List[int]) -> List[int]:
    """Multiplies two polynomials in NTT domain using BaseCaseMultiply."""
    c_hat = [0] * 256
    for i in range(128):
        c0, c1 = base_case_multiply(
            a_hat[2 * i], a_hat[2 * i + 1],
            b_hat[2 * i], b_hat[2 * i + 1],
            GAMMAS[i]
        )
        c_hat[2 * i] = c0
        c_hat[2 * i + 1] = c1
    return c_hat


def poly_add(a: List[int], b: List[int]) -> List[int]:
    """Coefficient-wise addition modulo q."""
    return [(x + y) % MLKEM_Q for x, y in zip(a, b)]


def poly_sub(a: List[int], b: List[int]) -> List[int]:
    """Coefficient-wise subtraction modulo q."""
    return [(x - y) % MLKEM_Q for x, y in zip(a, b)]


# ==============================================================================
# Sampling Primitives (SampleNTT & SamplePolyCBD)
# ==============================================================================
def sample_ntt(rho: bytes, j: int, i: int) -> List[int]:
    """SHAKE-128 rejection sampling mod q for matrix A entry A[i][j].

    According to NIST FIPS 203, input seed is rho || j || i.
    Dynamically expands digest to prevent stalling.
    """
    ctx = hashlib.shake_128(rho + bytes([j, i]))
    buf_len = 672
    buf = ctx.digest(buf_len)
    coeffs: List[int] = []
    pos = 0
    while len(coeffs) < 256:
        if pos + 3 > len(buf):
            buf_len += 168
            buf = ctx.digest(buf_len)
        b0, b1, b2 = buf[pos], buf[pos + 1], buf[pos + 2]
        pos += 3
        d1 = b0 + 256 * (b1 & 0x0F)
        d2 = (b1 >> 4) + 16 * b2
        if d1 < MLKEM_Q:
            coeffs.append(d1)
        if len(coeffs) < 256 and d2 < MLKEM_Q:
            coeffs.append(d2)
    return coeffs


def sample_poly_cbd(sigma: bytes, n: int, eta: int = 2) -> List[int]:
    """SHAKE-256 Centered Binomial Distribution sampling with parameter eta=2."""
    ctx = hashlib.shake_256(sigma + bytes([n]))
    buf = ctx.digest(64 * eta)
    coeffs: List[int] = []
    for b in buf:
        b0 = b & 1
        b1 = (b >> 1) & 1
        b2 = (b >> 2) & 1
        b3 = (b >> 3) & 1
        coeffs.append((b0 + b1 - b2 - b3) % MLKEM_Q)
        b4 = (b >> 4) & 1
        b5 = (b >> 5) & 1
        b6 = (b >> 6) & 1
        b7 = (b >> 7) & 1
        coeffs.append((b4 + b5 - b6 - b7) % MLKEM_Q)
    return coeffs


# ==============================================================================
# Byte Encoding, Decoding, Compression, and Decompression
# ==============================================================================
def compress(x: int, d: int) -> int:
    """Compresses x in Z_q to d bits: round(2^d / q * x) mod 2^d."""
    return (((x << d) + MLKEM_Q // 2) // MLKEM_Q) & ((1 << d) - 1)


def decompress(y: int, d: int) -> int:
    """Decompresses y in [0, 2^d - 1] to Z_q: round(q / 2^d * y)."""
    return ((y * MLKEM_Q) + (1 << (d - 1))) >> d


def byte_encode_12(poly: List[int]) -> bytes:
    """Encodes 256 12-bit integers into 384 bytes."""
    b = bytearray(384)
    for i in range(128):
        x = poly[2 * i] & 0xFFF
        y = poly[2 * i + 1] & 0xFFF
        b[3 * i] = x & 0xFF
        b[3 * i + 1] = (x >> 8) | ((y & 0x0F) << 4)
        b[3 * i + 2] = (y >> 4) & 0xFF
    return bytes(b)


def byte_decode_12(data: bytes) -> List[int]:
    """Decodes 384 bytes into 256 12-bit integers."""
    poly = [0] * 256
    for i in range(128):
        b0 = data[3 * i]
        b1 = data[3 * i + 1]
        b2 = data[3 * i + 2]
        poly[2 * i] = b0 | ((b1 & 0x0F) << 8)
        poly[2 * i + 1] = (b1 >> 4) | (b2 << 4)
    return poly


def byte_encode_10(poly: List[int]) -> bytes:
    """Encodes 256 10-bit integers into 320 bytes."""
    b = bytearray(320)
    for i in range(64):
        p0 = poly[4 * i] & 0x3FF
        p1 = poly[4 * i + 1] & 0x3FF
        p2 = poly[4 * i + 2] & 0x3FF
        p3 = poly[4 * i + 3] & 0x3FF
        b[5 * i] = p0 & 0xFF
        b[5 * i + 1] = (p0 >> 8) | ((p1 & 0x3F) << 2)
        b[5 * i + 2] = (p1 >> 6) | ((p2 & 0x0F) << 4)
        b[5 * i + 3] = (p2 >> 4) | ((p3 & 0x03) << 6)
        b[5 * i + 4] = (p3 >> 2) & 0xFF
    return bytes(b)


def byte_decode_10(data: bytes) -> List[int]:
    """Decodes 320 bytes into 256 10-bit integers."""
    poly = [0] * 256
    for i in range(64):
        b = data[5 * i : 5 * i + 5]
        poly[4 * i] = b[0] | ((b[1] & 0x03) << 8)
        poly[4 * i + 1] = (b[1] >> 2) | ((b[2] & 0x0F) << 6)
        poly[4 * i + 2] = (b[2] >> 4) | ((b[3] & 0x3F) << 4)
        poly[4 * i + 3] = (b[3] >> 6) | (b[4] << 2)
    return poly


def byte_encode_4(poly: List[int]) -> bytes:
    """Encodes 256 4-bit integers into 128 bytes."""
    b = bytearray(128)
    for i in range(128):
        x = poly[2 * i] & 0x0F
        y = poly[2 * i + 1] & 0x0F
        b[i] = x | (y << 4)
    return bytes(b)


def byte_decode_4(data: bytes) -> List[int]:
    """Decodes 128 bytes into 256 4-bit integers."""
    poly = [0] * 256
    for i in range(128):
        b = data[i]
        poly[2 * i] = b & 0x0F
        poly[2 * i + 1] = b >> 4
    return poly


def byte_encode_1(poly: List[int]) -> bytes:
    """Encodes 256 1-bit integers into 32 bytes."""
    b = bytearray(32)
    for i in range(32):
        byte = 0
        for j in range(8):
            byte |= (poly[8 * i + j] & 1) << j
        b[i] = byte
    return bytes(b)


def byte_decode_1(data: bytes) -> List[int]:
    """Decodes 32 bytes into 256 1-bit integers."""
    poly = [0] * 256
    for i in range(32):
        b = data[i]
        for j in range(8):
            poly[8 * i + j] = (b >> j) & 1
    return poly


def byte_encode(poly: List[int], bits: int) -> bytes:
    """Generic byte encoder supporting 12, 10, 4, and 1 bits."""
    if bits == 12:
        return byte_encode_12(poly)
    elif bits == 10:
        return byte_encode_10(poly)
    elif bits == 4:
        return byte_encode_4(poly)
    elif bits == 1:
        return byte_encode_1(poly)
    else:
        raise ValueError(f"Unsupported bit depth: {bits}")


def byte_decode(data: bytes, bits: int) -> List[int]:
    """Generic byte decoder supporting 12, 10, 4, and 1 bits."""
    if bits == 12:
        return byte_decode_12(data)
    elif bits == 10:
        return byte_decode_10(data)
    elif bits == 4:
        return byte_decode_4(data)
    elif bits == 1:
        return byte_decode_1(data)
    else:
        raise ValueError(f"Unsupported bit depth: {bits}")


# ==============================================================================
# Public Key Encryption (ML-KEM-CPAPKE)
# ==============================================================================
def k_pke_keygen(d: bytes) -> Tuple[bytes, bytes]:
    """K-PKE Key Generation (FIPS 203 Algorithm 13)."""
    g = hashlib.sha3_512(d + bytes([MLKEM_K])).digest()
    rho, sigma = g[:32], g[32:]
    A_hat = [[sample_ntt(rho, j, i) for j in range(MLKEM_K)] for i in range(MLKEM_K)]
    s = [sample_poly_cbd(sigma, i, MLKEM_ETA1) for i in range(MLKEM_K)]
    e = [sample_poly_cbd(sigma, MLKEM_K + i, MLKEM_ETA1) for i in range(MLKEM_K)]
    s_hat = [ntt(s[i]) for i in range(MLKEM_K)]
    e_hat = [ntt(e[i]) for i in range(MLKEM_K)]
    t_hat = []
    for i in range(MLKEM_K):
        row_sum = [0] * 256
        for j in range(MLKEM_K):
            prod = multiply_ntts(A_hat[i][j], s_hat[j])
            row_sum = poly_add(row_sum, prod)
        t_hat.append(poly_add(row_sum, e_hat[i]))
    ek_pke = b"".join(byte_encode_12(t_hat[i]) for i in range(MLKEM_K)) + rho
    dk_pke = b"".join(byte_encode_12(s_hat[i]) for i in range(MLKEM_K))
    return ek_pke, dk_pke


def k_pke_encrypt(ek_pke: bytes, m: bytes, r: bytes) -> bytes:
    """K-PKE Encryption (FIPS 203 Algorithm 14)."""
    t_hat = [byte_decode_12(ek_pke[i * 384 : (i + 1) * 384]) for i in range(MLKEM_K)]
    rho = ek_pke[384 * MLKEM_K : 384 * MLKEM_K + 32]
    # A^T[i][j] = A[j][i] = sample_ntt(rho, i, j)
    A_T_hat = [[sample_ntt(rho, i, j) for j in range(MLKEM_K)] for i in range(MLKEM_K)]
    y = [sample_poly_cbd(r, i, MLKEM_ETA1) for i in range(MLKEM_K)]
    e1 = [sample_poly_cbd(r, MLKEM_K + i, MLKEM_ETA2) for i in range(MLKEM_K)]
    e2 = sample_poly_cbd(r, 2 * MLKEM_K, MLKEM_ETA2)
    y_hat = [ntt(y[i]) for i in range(MLKEM_K)]
    u = []
    for i in range(MLKEM_K):
        row_sum = [0] * 256
        for j in range(MLKEM_K):
            prod = multiply_ntts(A_T_hat[i][j], y_hat[j])
            row_sum = poly_add(row_sum, prod)
        u.append(poly_add(intt(row_sum), e1[i]))

    ty_sum = [0] * 256
    for i in range(MLKEM_K):
        ty_sum = poly_add(ty_sum, multiply_ntts(t_hat[i], y_hat[i]))
    mu = [decompress(b, 1) for b in byte_decode_1(m)]
    v = poly_add(poly_add(intt(ty_sum), e2), mu)

    c1 = b"".join(byte_encode_10([compress(x, MLKEM_DU) for x in u[i]]) for i in range(MLKEM_K))
    c2 = byte_encode_4([compress(x, MLKEM_DV) for x in v])
    return c1 + c2


def k_pke_decrypt(dk_pke: bytes, c: bytes) -> bytes:
    """K-PKE Decryption (FIPS 203 Algorithm 15)."""
    s_hat = [byte_decode_12(dk_pke[i * 384 : (i + 1) * 384]) for i in range(MLKEM_K)]
    u = [[decompress(x, MLKEM_DU) for x in byte_decode_10(c[i * 320 : (i + 1) * 320])] for i in range(MLKEM_K)]
    v = [decompress(x, MLKEM_DV) for x in byte_decode_4(c[320 * MLKEM_K : 320 * MLKEM_K + 128])]
    u_hat = [ntt(u[i]) for i in range(MLKEM_K)]
    su_sum = [0] * 256
    for i in range(MLKEM_K):
        su_sum = poly_add(su_sum, multiply_ntts(s_hat[i], u_hat[i]))
    w = poly_sub(v, intt(su_sum))
    m = byte_encode_1([compress(x, 1) for x in w])
    return m


# ==============================================================================
# ML-KEM-CCA Key Encapsulation Mechanism (FIPS 203 Section 6)
# ==============================================================================
def mlkem768_keygen() -> Tuple[bytes, bytes]:
    """Generates an ML-KEM-768 keypair.

    Returns:
        (ek, dk): 1184-byte encapsulation key and 2400-byte decapsulation key.
    """
    d = secrets.token_bytes(32)
    z = secrets.token_bytes(32)
    ek, dk_pke = k_pke_keygen(d)
    h_ek = hashlib.sha3_256(ek).digest()
    dk = dk_pke + ek + h_ek + z
    return ek, dk


def mlkem768_encaps(ek: bytes) -> Tuple[bytes, bytes]:
    """Encapsulates a shared secret using encapsulation key ek.

    Returns:
        (ciphertext, shared_secret): 1088-byte ciphertext and 32-byte shared secret.
    """
    if len(ek) != MLKEM_EK_BYTES:
        raise ValueError(f"Invalid ML-KEM-768 encapsulation key length: {len(ek)} (expected {MLKEM_EK_BYTES})")
    m = secrets.token_bytes(32)
    h_ek = hashlib.sha3_256(ek).digest()
    g = hashlib.sha3_512(m + h_ek).digest()
    K, r = g[:32], g[32:]
    c = k_pke_encrypt(ek, m, r)
    return c, K


def mlkem768_decaps(dk: bytes, ct: bytes) -> bytes:
    """Decapsulates shared secret with Fujisaki-Okamoto implicit rejection.

    Returns 32-byte shared secret.
    """
    if len(dk) != MLKEM_DK_BYTES:
        raise ValueError(f"Invalid ML-KEM-768 decapsulation key length: {len(dk)} (expected {MLKEM_DK_BYTES})")
    if len(ct) != MLKEM_CT_BYTES:
        raise ValueError(f"Invalid ML-KEM-768 ciphertext length: {len(ct)} (expected {MLKEM_CT_BYTES})")

    dk_pke = dk[:384 * MLKEM_K]
    ek = dk[384 * MLKEM_K : 384 * MLKEM_K + 1184]
    h_ek = dk[384 * MLKEM_K + 1184 : 384 * MLKEM_K + 1184 + 32]
    z = dk[384 * MLKEM_K + 1184 + 32 : 384 * MLKEM_K + 1184 + 64]

    m_prime = k_pke_decrypt(dk_pke, ct)
    g = hashlib.sha3_512(m_prime + h_ek).digest()
    K_prime, r_prime = g[:32], g[32:]
    c_prime = k_pke_encrypt(ek, m_prime, r_prime)

    if secrets.compare_digest(ct, c_prime):
        return K_prime
    else:
        # Implicit rejection fallback key derived from rejection seed z and ciphertext
        return hashlib.shake_256(z + ct).digest(32)


class MLKEM768:
    """Object-oriented wrapper for ML-KEM-768 operations."""

    EK_BYTES = MLKEM_EK_BYTES
    DK_BYTES = MLKEM_DK_BYTES
    CT_BYTES = MLKEM_CT_BYTES
    SS_BYTES = MLKEM_SS_BYTES

    @staticmethod
    def keygen() -> Tuple[bytes, bytes]:
        return mlkem768_keygen()

    @staticmethod
    def encaps(ek: bytes) -> Tuple[bytes, bytes]:
        return mlkem768_encaps(ek)

    @staticmethod
    def decaps(dk: bytes, ct: bytes) -> bytes:
        return mlkem768_decaps(dk, ct)
