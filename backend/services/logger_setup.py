import logging
import sys
from datetime import datetime
import os
import builtins

def setup_logging():
    LOG_DIR = "logs"
    os.makedirs(LOG_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    LOG_FILE = os.path.join(LOG_DIR, f"etl_{timestamp}.log")

    logger = logging.getLogger()
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )

    # file
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # redirect print → logger
    def hooked_print(*args, **kwargs):
        message = " ".join(str(a) for a in args)
        logger.info(message)

    builtins.print = hooked_print   # <-- The correct global override

    return logger
