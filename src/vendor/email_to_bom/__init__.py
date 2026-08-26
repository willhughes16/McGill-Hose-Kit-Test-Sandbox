"""Email -> Bill of Materials agent (McGill Hose & Coupling, TWYD Factory RA1).

AUTO rules only live in this package. Checkpoint-gated actions (QC material
verification, length confirmation, quote send) are HARNESS-HELD and deliberately
absent from this toolset (RA1 containment).
"""
from .core import Agent, load_config

__all__ = ["Agent", "load_config"]
