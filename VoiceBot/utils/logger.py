# Path: utils/logger.py
import logging
from rich.logging import RichHandler
from utils.ui import console

def get_logger(name: str) -> logging.Logger:
    """Returns a configured logger instance using Rich."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        # Console handler with Rich
        ch = RichHandler(console=console, rich_tracebacks=True, show_time=True, show_level=True, show_path=False, markup=True)
        # We don't need the standard formatter's time and level since Rich handles it
        formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
    return logger