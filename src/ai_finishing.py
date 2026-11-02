"""Compatibility import for the Gurumoji package module."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module("gurumoji.ai_finishing")
