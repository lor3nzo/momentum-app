"""Backend utilities for the momentum scoring application.

This package exposes common functions used by the FastAPI backend and other
modules. Importing these helpers at the package level provides a clear and
concise path for consumers.
"""

from .momentum import compute_scores

__all__ = ["compute_scores"]
