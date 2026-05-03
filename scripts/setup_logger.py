"""Setup logging for scripts."""

import datetime
import logging
import resource
from pathlib import Path


def configure_logging(script_name: str) -> None:
    """Configure logging for scripts.

    Sets up logging format and logging file.

    Args:
        script_name: Name of the script that's running, usually `__file__`.

    """
    logging.getLogger("py.warnings")
    logging.captureWarnings(capture=True)

    now = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    logging.basicConfig(
        filename=f"/home/health/output/{Path(script_name).stem}_{now}.log",
        level=logging.INFO,
        force=True,
        format="%(asctime)s %(name)s[%(process)d] %(levelname)s %(message)s",
    )


def log_peak_memory(logger: logging.Logger) -> None:
    """Log peak memory usage."""
    kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    logger.info("Peak memory: %.1f MB", kb / 1024)
