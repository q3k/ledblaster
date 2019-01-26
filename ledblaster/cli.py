import logging
import sys

from migen.build.xilinx.programmer import XC3SProg

import ledblaster
from ledblaster.gateware.platforms.rv901t import Platform, hub75e
from ledblaster.gateware.targets.rv901t import Target


logger = logging.getLogger(__name__)


class ANSIColorFormatter(logging.Formatter):
    LOG_COLORS = {
        "TRACE"   : "\033[37m",
        "DEBUG"   : "\033[36m",
        "INFO"    : "\033[1;37m",
        "WARNING" : "\033[1;33m",
        "ERROR"   : "\033[1;31m",
        "CRITICAL": "\033[1;41m",
    }

    def format(self, record):
        color = self.LOG_COLORS.get(record.levelname, "")
        return "{}{}\033[0m".format(color, super().format(record))


def main():
    handler = logging.StreamHandler()

    formatter_args = {"fmt": "{levelname[0]:s}: {name:s}: {message:s}", "style": "{"}
    if sys.stderr.isatty() and sys.platform != 'win32':
        handler.setFormatter(ANSIColorFormatter(**formatter_args))
    else:
        handler.setFormatter(logging.Formatter(**formatter_args))

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)


    logger.info("ledblaster version {}".format(ledblaster.__version__))

    logger.info("building gateware...")
    platform = Platform()
    platform.add_extension(hub75e)

    target = Target(platform)
    platform.build(target)

    logger.info("loading gateware...")
    prog = XC3SProg('xpc')
    prog.load_bitstream('build/top.bit')

    return 0
