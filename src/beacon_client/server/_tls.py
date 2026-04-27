from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_DIR = Path("/tmp/beacon_certs")
CERT_PATH = CERT_DIR / "server.crt"
KEY_PATH = CERT_DIR / "server.key"

DEFAULT_SAN = [
    "localhost",
    "api-server",
    "http2-server",
    "http3-server",
    "beacon-client",
]


def ensure_self_signed_cert(common_name: str = "beacon.local") -> tuple[Path, Path]:
    if CERT_PATH.exists() and KEY_PATH.exists():
        return CERT_PATH, KEY_PATH

    CERT_DIR.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)],
    )

    san_entries = [x509.DNSName(name) for name in DEFAULT_SAN]
    if common_name not in DEFAULT_SAN:
        san_entries.append(x509.DNSName(common_name))

    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private_key=private_key, algorithm=hashes.SHA256())
    )

    KEY_PATH.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )
    CERT_PATH.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))

    return CERT_PATH, KEY_PATH
