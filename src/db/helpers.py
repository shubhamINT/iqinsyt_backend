import hashlib
from datetime import datetime, timezone


def make_cache_key(event_title: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title_hash = hashlib.sha256(event_title.strip().lower().encode()).hexdigest()[:16]
    return f"{title_hash}:{date_str}"


def user_fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()
