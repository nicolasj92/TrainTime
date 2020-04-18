import requests
import time
import os
import logging
import django
import socket
import sys
from enum import Enum

from display_control.utils import Display

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pitraintime.settings")
django.setup()

from pitraintime.models import Connection, Station
from pitraintime.views import get_connections
from pitraintime.utils.config import TrainTimeConfig


def get_lock(process_name):
    # Without holding a reference to our socket somewhere it gets garbage
    # collected when the function exits
    get_lock._lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    try:
        # The null byte (\0) means the the socket is created
        # in the abstract namespace instead of being created
        # on the file system itself.
        # Works only in Linux
        get_lock._lock_socket.bind("\0" + process_name)
        print("I got the lock")
    except socket.error:
        sys.exit()


class Modes(Enum):
    TRAINTIMES = 1
    WORDCLOCK = 2
    TEXT = 3
    LARGECLOCK = 4
    DATETIME = 5


class DisplayControl:
    def __init__(self, logger, interval=0.05, mode=Modes.TRAINTIMES):
        self.logger = logger
        self.interval = interval
        self.display = Display(interval)
        self.logger.info("Initialized!")
        self.mode = mode

    @staticmethod
    def _check_network():
        url = "http://www.google.com/"
        timeout = 5
        try:
            requests.get(url, timeout=timeout)
            return True
        except requests.ConnectionError:
            return False

    def _show_error(self, message):
        self.logger.error(message)
        self.display.print_error(message)

    def run(self):
        # Clear RGB Matrix
        self.logger.info("Clearing display!")

        # Run forever or until errors occur
        last_log_timestamp = None
        self.logger.info("Starting loop!")
        while True:
            # Once in a while say hello
            if last_log_timestamp is None or (time.time() - last_log_timestamp) > 3600:
                self.logger.info("I am still here!")
                last_log_timestamp = time.time()

            # Check if network is up
            if not self._check_network():
                self._show_error("No Connection")
                continue

            if self.mode == Modes.TRAINTIMES:
                # Get connections
                route_information = [route for route in get_connections(3)]
                # Print connections to RGB Matrix
                self.display.print_connections(route_information)

            elif self.mode == Modes.WORDCLOCK:
                pass
            elif self.mode == Modes.LARGECLOCK:
                pass
            elif self.mode == Modes.DATETIME:
                pass
            else:
                raise ValueError("Mode not understood!")


if __name__ == "__main__":
    # Check of we are already running
    get_lock("traintime_display_daemon")

    # Initialize logging
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%d.%m.%Y %H:%M:%S",
    )
    logger = logging.getLogger("DisplayControl")

    # Intialize Display Controller
    display_controller = DisplayControl(logger=logger)

    # Run Display Controller
    display_controller.run()
