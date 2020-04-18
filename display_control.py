import requests
import time
import os
import logging
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pitraintime.settings")
django.setup()

from pitraintime.models import Connection, Station
from pitraintime.views import get_connections
from pitraintime.utils.config import TrainTimeConfig


class DisplayControl:
    def __init__(self, logger, interval=0.1):
        self.logger = logger
        self.interval = interval

        self.logger.info("Initialized!")

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
        # TODO show error on matrix

    def run(self):
        # Clear RGB Matrix
        self.logger.info("Clearing display!")

        # Run forever or until errors occur
        last_log_timestamp = None
        self.logger.info("Starting loop!")
        while True:
            # Check if network is up
            if not self._check_network():
                self._show_error("No Connection!")
                break

            # Get connections
            route_information = [route for route in get_connections(3)]

            # Validate connections
            # TODO

            # Print connections to RGB Matrix

            # Sleep for some time
            if last_log_timestamp is None or (time.time() - last_log_timestamp) > 60:
                self.logger.info("I am still here!")
                last_log_timestamp = time.time()
            time.sleep(self.interval)


if __name__ == "__main__":
    # Initialize logging
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%d.%m.%Y %H:%M:%S",
    )
    logger = logging.getLogger("DisplayControl")

    # Intialize RGB Matrix

    # Intialize Display Controller
    display_controller = DisplayControl(logger=logger)

    # Run Display Controller
    display_controller.run()
