import sys
from pathlib import Path
import logging


def setup_logging(log_file: str = None) -> None:
    """Sets up logging output.

    Parameters
    ----------
    log_file: str
        Setup path to log file.
    """
    # create handlers list
    handlers = list()

    # create file write handler if log file specified
    if log_file:
        # get log file path
        log_file_path = Path(log_file).resolve()

        # create path to log if needed
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # append to handlers
        handlers.append(logging.FileHandler(str(log_file_path), mode="w"))  # will overwrite logs if they exist at path

    # add stdout streaming to handlers
    handlers.append(logging.StreamHandler(sys.stdout))

    # setup log output config
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", handlers=handlers)
