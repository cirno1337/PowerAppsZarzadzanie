"""Logging configuration.

Per SECURITY.md "Logging policy": job lifecycle events at INFO, adapter call
details at DEBUG, and NEVER environment variable values, full Copilot
prompts/responses, or full normalized snapshots at any level.
"""

from __future__ import annotations

import logging


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
