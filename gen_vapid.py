import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

def generate_vapid_keys():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    
    # Private Key
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    # The library expects the raw private key in some cases, or the PEM. 
    # pywebpush usually wants it base64 encoded.
    
    # Public Key
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    
    # Remove PEM headers and base64 encode
    priv_b64 = base64.urlsafe_b64encode(private_bytes).decode().rstrip("=")
    pub_b64 = base64.urlsafe_b64encode(public_bytes).decode().rstrip("=")
    
    print(f"VAPID_PRIVATE_KEY={priv_b64}")
    print(f"VAPID_PUBLIC_KEY={pub_b64}")

if __name__ == "__main__":
    generate_vapid_keys()
