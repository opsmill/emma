"""Init file for Emma, mainly used to grab version from Poetry file."""

# FIXME: For some reason importlib.metadata isn't install when building the docker
# https://github.com/python-poetry/poetry/issues/2102
# Thus the application is broken as it can find the package ...
# import importlib.metadata
# __version__ = importlib.metadata.version("emma")

__version__ = "0.2.0"
