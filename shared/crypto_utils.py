import base64
import hashlib
from typing import TypedDict, Any
from cryptography.hazmat.primitives.serialization import load_ssh_public_key
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519, dsa, ec


class SSHKeyInfo(TypedDict):
    raw_key: str
    algorithm: str
    bits: int
    fingerprint: str
    comment: str


def validate_and_fingerprint_ssh_key(raw_key: str) -> dict[str, Any]:
    """
    Parses and validates an OpenSSH public key.
    Enforces whitelist: ssh-ed25519 or rsa-sha2-512 / rsa-sha2-256 / ssh-rsa with key size >= 3072.
    Rejects weak algorithms (DSA, RSA < 3072, EC, etc.).
    Calculates SHA-256 fingerprint matching standard `ssh-keygen -lf` format (SHA256:<base64>).
    Returns dict containing metadata.
    """
    if not raw_key or not isinstance(raw_key, str):
        raise ValueError("Public key must be a non-empty string.")

    cleaned_key = raw_key.strip()
    parts = cleaned_key.split(maxsplit=2)
    if len(parts) < 2:
        raise ValueError("Invalid OpenSSH public key format.")

    key_type_str = parts[0]
    comment = parts[2] if len(parts) > 2 else ""

    # Decode base64 key blob first to validate base64 and compute fingerprint
    try:
        raw_b64 = parts[1]
        raw_binary = base64.b64decode(raw_b64, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 payload in key: {e}")

    # Parse key bytes for cryptography library
    parse_key_str = cleaned_key
    if key_type_str in ("rsa-sha2-512", "rsa-sha2-256"):
        parse_key_str = f"ssh-rsa {parts[1]}"
        if comment:
            parse_key_str += f" {comment}"

    try:
        key_bytes = parse_key_str.encode("utf-8")
        public_key = load_ssh_public_key(key_bytes)
    except Exception as e:
        raise ValueError(f"Failed to parse SSH public key: {e}")

    # Compute SHA-256 fingerprint
    digest = hashlib.sha256(raw_binary).digest()
    fp_b64 = base64.b64encode(digest).decode("utf-8").rstrip("=")
    fingerprint = f"SHA256:{fp_b64}"

    bits = 0
    algorithm = key_type_str

    if isinstance(public_key, ed25519.Ed25519PublicKey):
        bits = 256
        if key_type_str != "ssh-ed25519":
            raise ValueError(f"Key type mismatch for Ed25519: {key_type_str}")
    elif isinstance(public_key, rsa.RSAPublicKey):
        bits = public_key.key_size
        if key_type_str not in ("rsa-sha2-512", "rsa-sha2-256", "ssh-rsa"):
            raise ValueError(f"Unsupported RSA algorithm type: {key_type_str}")
        if bits < 3072:
            raise ValueError(f"RSA key size must be at least 3072 bits (got {bits}).")
    elif isinstance(public_key, dsa.DSAPublicKey):
        raise ValueError("DSA keys (ssh-dss) are insecure and not allowed.")
    elif isinstance(public_key, ec.EllipticCurvePublicKey):
        raise ValueError(f"ECDSA key type '{key_type_str}' is not in whitelist.")
    else:
        raise ValueError(f"Unsupported SSH key algorithm: {type(public_key).__name__}")

    return {
        "raw_key": cleaned_key,
        "algorithm": algorithm,
        "bits": bits,
        "fingerprint": fingerprint,
        "comment": comment,
    }
