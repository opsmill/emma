import os
import uuid
from typing import List


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


# Could be moved to the SDK later on
def parse_hfid(hfid: str) -> List[str]:
    """Parse a single HFID string into its components if it contains '__'."""
    return hfid.split("__") if "__" in hfid else [hfid]


def is_feature_enabled(feature_name: str) -> bool:
    """Feature flags implementation"""
    feature_flags = {}
    feature_flags_env = os.getenv("EMMA_FEATURE_FLAGS", "")
    if feature_flags_env:
        for feature in feature_flags_env.split(","):
            feature_flags[feature.strip()] = True
    return feature_flags.get(feature_name, False)
