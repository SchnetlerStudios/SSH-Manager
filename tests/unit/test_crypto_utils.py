import pytest
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519, dsa, ec
from cryptography.hazmat.primitives import serialization
from shared.crypto_utils import validate_and_fingerprint_ssh_key


def generate_ed25519_key_str(comment: str = "user@test") -> str:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    return f"{pub_bytes.decode('utf-8')} {comment}"


def generate_rsa_key_str(bits: int, key_type: str = "ssh-rsa", comment: str = "rsa@test") -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    parts = pub_bytes.decode("utf-8").split()
    return f"{key_type} {parts[1]} {comment}"


def generate_dsa_key_str(comment: str = "dsa@test") -> str:
    private_key = dsa.generate_private_key(key_size=1024)
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    return f"{pub_bytes.decode('utf-8')} {comment}"


def test_validate_valid_ed25519():
    key_str = generate_ed25519_key_str(comment="dev@example.com")
    res = validate_and_fingerprint_ssh_key(key_str)
    assert res["algorithm"] == "ssh-ed25519"
    assert res["bits"] == 256
    assert res["comment"] == "dev@example.com"
    assert res["fingerprint"].startswith("SHA256:")


def test_validate_valid_rsa_4096():
    key_str = generate_rsa_key_str(4096, key_type="rsa-sha2-512", comment="admin@example.com")
    res = validate_and_fingerprint_ssh_key(key_str)
    assert res["algorithm"] == "rsa-sha2-512"
    assert res["bits"] == 4096
    assert res["comment"] == "admin@example.com"
    assert res["fingerprint"].startswith("SHA256:")


def test_validate_valid_rsa_3072_ssh_rsa():
    key_str = generate_rsa_key_str(3072, key_type="ssh-rsa")
    res = validate_and_fingerprint_ssh_key(key_str)
    assert res["bits"] == 3072


def test_reject_weak_rsa_1024():
    key_str = generate_rsa_key_str(1024)
    with pytest.raises(ValueError, match="at least 3072 bits"):
        validate_and_fingerprint_ssh_key(key_str)


def test_reject_dsa_key():
    key_str = generate_dsa_key_str()
    with pytest.raises(ValueError, match="DSA keys"):
        validate_and_fingerprint_ssh_key(key_str)


def test_invalid_and_malformed_keys():
    with pytest.raises(ValueError, match="non-empty string"):
        validate_and_fingerprint_ssh_key("")

    with pytest.raises(ValueError, match="non-empty string"):
        validate_and_fingerprint_ssh_key(None)

    with pytest.raises(ValueError, match="Invalid OpenSSH public key format"):
        validate_and_fingerprint_ssh_key("invalid_key_format")

    with pytest.raises(ValueError, match="Invalid base64 payload"):
        validate_and_fingerprint_ssh_key("ssh-ed25519 INVALID_BASE64_DATA comment")

    with pytest.raises(ValueError, match="Invalid base64 payload"):
        validate_and_fingerprint_ssh_key("ssh-rsa !@#$%^&*() comment")


def test_unsupported_key_class(monkeypatch):
    key_str = generate_ed25519_key_str()
    monkeypatch.setattr("shared.crypto_utils.load_ssh_public_key", lambda x: UnknownKeyType())
    with pytest.raises(ValueError, match="Unsupported SSH key algorithm"):
        validate_and_fingerprint_ssh_key(key_str)


class UnknownKeyType:
    pass


def test_ed25519_key_type_mismatch():
    key_str = generate_ed25519_key_str()
    parts = key_str.split()
    mismatched = f"ssh-rsa {parts[1]} comment"
    with pytest.raises(ValueError, match="Failed to parse SSH public key"):
        validate_and_fingerprint_ssh_key(mismatched)


def test_ed25519_key_type_mismatch_with_ed25519_instance(monkeypatch):
    key_str = generate_ed25519_key_str()
    parts = key_str.split()
    mismatched = f"ssh-other {parts[1]} {parts[2] if len(parts)>2 else ''}"
    private_key = ed25519.Ed25519PrivateKey.generate()
    monkeypatch.setattr("shared.crypto_utils.load_ssh_public_key", lambda x: private_key.public_key())
    with pytest.raises(ValueError, match="Key type mismatch for Ed25519"):
        validate_and_fingerprint_ssh_key(mismatched)


def test_rsa_unsupported_algorithm_type_with_rsa_instance(monkeypatch):
    key_str = generate_rsa_key_str(3072, key_type="ssh-rsa")
    parts = key_str.split()
    mismatched = f"unsupported-rsa-type {parts[1]} {parts[2] if len(parts)>2 else ''}"
    private_key = rsa.generate_private_key(65537, 3072)
    monkeypatch.setattr("shared.crypto_utils.load_ssh_public_key", lambda x: private_key.public_key())
    with pytest.raises(ValueError, match="Unsupported RSA algorithm type"):
        validate_and_fingerprint_ssh_key(mismatched)


def test_unsupported_rsa_algorithm_type():
    key_str = generate_rsa_key_str(3072, key_type="ssh-unknown-rsa")
    with pytest.raises(ValueError, match="Failed to parse SSH public key"):
        validate_and_fingerprint_ssh_key(key_str)


def test_ecdsa_key_type_rejected():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    key_str = pub_bytes.decode("utf-8")
    with pytest.raises(ValueError, match="not in whitelist"):
        validate_and_fingerprint_ssh_key(key_str)
