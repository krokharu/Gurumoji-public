"""Compatibility import for development tools that import ``app`` directly."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module("gurumoji.app")
