"""Init file for Emma, mainly used to grab version from Poetry file."""

import importlib.metadata

__version__ = importlib.metadata.version("emma")
