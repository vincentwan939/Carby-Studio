"""
Carby Sprint - CLI for sprint management with validation gates.

A production-ready CLI tool for managing sprints with integrated
validation gates, documentation compliance, and parallel execution.
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Carby Studio"
__license__ = "MIT"

from .cli import cli

__all__ = ["cli"]
