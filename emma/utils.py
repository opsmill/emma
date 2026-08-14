import os
import uuid
from typing import Any, List


def is_uuid(value: Any) -> bool:
    """Check whether a value is a UUID.

    Args:
        value: The value to check. Non-string input (a number parsed out of a CSV
            cell, for instance) is simply not a UUID rather than an error.

    Returns:
        True if the value parses as a UUID.
    """
    try:
        uuid.UUID(value)
        return True
    except (AttributeError, TypeError, ValueError):
        return False


# TODO: Could be moved to the SDK later on
def parse_hfid(hfid: str) -> List[str]:
    """Parse a single HFID string into its components if it contains '__'."""
    parsed_hfid = hfid.split("__") if "__" in hfid else [hfid]
    return parsed_hfid


def is_feature_enabled(feature_name: str) -> bool:
    """Feature flags implementation"""
    feature_flags = {}
    feature_flags_env = os.getenv("EMMA_FEATURE_FLAGS", "")
    if feature_flags_env:
        for feature in feature_flags_env.split(","):
            feature_flags[feature.strip()] = True
    return feature_flags.get(feature_name, False)
