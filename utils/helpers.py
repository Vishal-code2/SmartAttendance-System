import hashlib
import json
import numpy as np
from typing import List

def hash_password(password: str) -> str:
    """Hash password using SHA-256 for basic admin authentication."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def serialize_encoding(encoding: np.ndarray) -> bytes:
    """Serialize numpy float encoding array into bytes for database storage."""
    return encoding.tobytes()

def deserialize_encoding(encoding_bytes: bytes) -> np.ndarray:
    """Deserialize bytes from database storage back into a numpy float array."""
    return np.frombuffer(encoding_bytes, dtype=np.float64)

def serialize_list(data: List[str]) -> str:
    """Serialize a list of strings into a JSON string."""
    return json.dumps(data)

def deserialize_list(json_str: str) -> List[str]:
    """Deserialize a JSON string back into a list of strings."""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return []
