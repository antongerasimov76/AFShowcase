"""
Shared utilities for cargo data validation and transformation.
"""
import re
import hashlib


def validate_shipment_id(shipment_id: str) -> bool:
    """Validate shipment ID format: alphanumeric with dashes, 8-20 chars."""
    return bool(re.match(r"^[A-Za-z0-9\-]{8,20}$", shipment_id))


def generate_idempotency_key(shipment_ids: list) -> str:
    """Generate a deterministic key for deduplication of batch requests."""
    combined = "|".join(sorted(shipment_ids))
    return hashlib.md5(combined.encode()).hexdigest()


def normalize_weight(value, unit: str) -> float:
    """Convert weight to kilograms."""
    conversions = {
        "kg": 1.0,
        "lbs": 0.453592,
        "lb": 0.453592,
        "oz": 0.0283495,
        "g": 0.001,
        "tons": 1000.0,
        "t": 1000.0
    }
    factor = conversions.get(unit.lower(), 1.0)
    return round(float(value) * factor, 3)


def sanitize_blob_name(name: str) -> str:
    """Remove invalid characters from blob names."""
    # Allow alphanumeric, dash, underscore, dot, forward slash
    return re.sub(r"[^A-Za-z0-9\-_./]", "", name)
