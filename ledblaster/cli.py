import logging

logger = logging.getLogger(__name__)

def main():
    root = logging.getLogger()
    root.addHandler(logging.StreamHandler())
    root.setLevel(logging.DEBUG)

    logger.info("ledblaster gateware...")
    return 0
