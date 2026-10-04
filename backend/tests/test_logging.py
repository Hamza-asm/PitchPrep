"""Application logs reach stdout without duplicated handlers."""

import io
import logging

from app.core.logging import configure_app_logging


def test_application_logging_writes_once_to_stdout() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("app")
    original_handlers = logger.handlers[:]
    original_level = logger.level
    original_propagate = logger.propagate
    try:
        logger.handlers = []
        configure_app_logging(stream)
        configure_app_logging(stream)
        logging.getLogger("app.workflows.research").info("Research stage started run_id=synthetic node=writer revision=0")
        assert stream.getvalue().count("node=writer") == 1
        assert "Research stage started" in stream.getvalue()
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate
