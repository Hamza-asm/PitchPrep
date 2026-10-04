"""Send application-owned, metadata-only logs to the hosting runtime."""

import logging
import sys
from typing import TextIO


def configure_app_logging(stream: TextIO | None = None) -> None:
    logger = logging.getLogger("app")
    if not any(handler.name == "pitchprep_stdout" for handler in logger.handlers):
        handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        handler.set_name("pitchprep_stdout")
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
