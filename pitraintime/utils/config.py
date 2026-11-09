import json

from django.conf import settings


class TrainTimeConfig(object):
    config_path = settings.CONFIG_FILEPATH

    def __init__(self):
        self.load(self.config_path)

    def load(self, path=None):
        if path is None:
            path = self.config_path
        with open(path, "r") as fh:
            config_dict = json.loads(fh.read())
        self.max_departures = config_dict["max_departures"]
        self.layout_type = config_dict["layout_type"]
        self.routes = config_dict["routes"]
        self.walk_time = config_dict["walk_time"]

    def save(self, path=None):
        if path is None:
            path = self.config_path
        config_dict = {
            "max_departures": self.max_departures,
            "layout_type": self.layout_type,
            "routes": self.routes,
            "walk_time": self.walk_time,
        }
        with open(path, "w") as fh:
            json.dump(config_dict, fh)

    def set_route(self, index, start, end):
        self.routes[index] = {"start": start, "end": end}
