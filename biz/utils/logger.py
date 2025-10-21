import logging

from .env import RuntimeEnv

nameToLevel = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET
}

logger = logging.getLogger("default-logger")
logger.setLevel(nameToLevel.get(RuntimeEnv.Instance().LOG_LEVEL, logging.NOTSET))
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)
