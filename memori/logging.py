import sys
from pathlib import Path
import logging
from typing import List
from subprocess import Popen, PIPE, STDOUT, DEVNULL


def run_process(cmd: List[str], stderr_to_stdout: bool = True) -> int:
    """Runs a shell command in a subprocess, but also log the output to stdout.

    Parameters
    ----------
    cmd : List[str]
        Command and arguments to run
    stderr_to_stdout : bool, optional
        If True, stderr will be redirected to stdout, otherwise it will be hidden, by default True

    Returns
    -------
    int
        Return code from process.
    """
    if stderr_to_stdout:
        stderr = STDOUT
    else:
        stderr = DEVNULL
    with Popen(cmd, stdout=PIPE, stderr=stderr, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:
            logging.info(line.rstrip())
        p.wait()
        return_value = p.returncode
    return return_value


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
