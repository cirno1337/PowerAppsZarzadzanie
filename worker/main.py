"""Worker entry point: polls SharePoint for PENDING jobs and processes them.

Run with ``python -m worker.main``. This process makes no assumption about
its host (see ARCHITECTURE.md "Deployment abstraction") — it can run in a
terminal, under a scheduled task, or wrapped as a service.

Usage:
    python -m worker.main             # continuous polling loop
    python -m worker.main --once      # process at most one pending job, then exit
"""

from __future__ import annotations

import argparse
import logging
import time

from worker.adapters.factory import (
    build_copilot_adapter,
    build_powerplatform_adapter,
    build_sharepoint_adapter,
)
from worker.config import load_config
from worker.job_processor import JobProcessor
from worker.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def build_job_processor() -> JobProcessor:
    config = load_config()
    sharepoint = build_sharepoint_adapter(config)
    powerplatform = build_powerplatform_adapter(config)
    copilot = build_copilot_adapter(config, sharepoint)
    return JobProcessor(
        powerplatform=powerplatform,
        sharepoint=sharepoint,
        copilot=copilot,
        worker_id=config.worker_id,
        max_retries=config.max_retries,
        export_dir=config.local_data_dir / "_exports",
        copilot_mode=config.copilot_mode,
    ), config


def main() -> None:
    parser = argparse.ArgumentParser(description="Power Platform Documentation Manager worker")
    parser.add_argument("--once", action="store_true", help="process at most one pending job, then exit")
    args = parser.parse_args()

    processor, config = build_job_processor()
    configure_logging(verbose=config.verbose_logging)
    logger.info(
        "Worker '%s' starting (powerplatform=%s, sharepoint=%s, copilot=%s)",
        config.worker_id,
        config.powerplatform_mode,
        config.sharepoint_mode,
        config.copilot_mode,
    )

    if args.once:
        job = processor.process_next()
        if job is None:
            logger.info("No pending jobs.")
        else:
            logger.info("Processed job %s -> %s", job.job_id, job.status.value)
        return

    logger.info("Polling every %.1fs. Press Ctrl+C to stop.", config.poll_interval_seconds)
    try:
        while True:
            job = processor.process_next()
            if job is None:
                time.sleep(config.poll_interval_seconds)
            else:
                logger.info("Processed job %s -> %s", job.job_id, job.status.value)
    except KeyboardInterrupt:
        logger.info("Worker stopped.")


if __name__ == "__main__":
    main()
