import time
import requests
import json
import network
import datetime
import pytz

from collections import namedtuple

Connection = namedtuple(
    "Connection", "station_id_start station_id_end time_at_start line_name line_direction vehicle_type"
)


class RmvAPIAccessor(object):
    def __init__(self, api_url: str, access_token: str) -> None:
        self.api_url = api_url
        self.access_token = access_token

    @staticmethod
    def _json_to_connection(obj, route):
        line_name = obj["Product"][0]["line"].strip()
        line_direction = obj["direction"].strip()
        vehicle_type = obj["Product"][0]["catOut"].strip()

        date = obj.get("rtDate", obj["date"]).strip()
        clock_time = obj.get("rtTime", obj["time"]).strip()
        time_string = date + " " + clock_time
        time_at_start = datetime.datetime.strptime(time_string, "%Y-%m-%d %H:%M:%S")

        return Connection(
            station_id_start=route["start"],
            station_id_end=route["end"],
            time_at_start=time_at_start,
            line_name=line_name,
            line_direction=line_direction,
            vehicle_type=vehicle_type,
        )

    def find_departures(self, route, from_timestamp=None, max_departures=10, duration=180):
        if from_timestamp is None:
            from_time = time.localtime()
        else:
            from_time = time.localtime(from_timestamp)

        year, month, day, hour, minute, _, _, _, _, = from_time
        actual_date = "{}-{:02}-{:02}".format(year, month, day)
        actual_time = "{:02}:{:02}".format(hour, minute)

        req = "{url}&accessId={token}&id={start}&direction={end}&date={date}&time={time}&maxJourneys={max_departures}&duration={duration}&format=json".format(
            url=self.api_url,
            token=self.access_token,
            start=route["start"],
            end=route["end"],
            date=actual_date,
            time=actual_time,
            max_departures=max_departures,
            duration=duration
        )

        print(req)

        get = requests.get(req)
        json_content = get.json()
        get.close()

        with open("sample_json.json", "w") as f:
            json.dump(json_content, f, indent=4)

        try:
            connections = [
                self._json_to_connection(json_content["Departure"][i], route)
                for i in range(len(json_content["Departure"]))
            ]
        except KeyError as err:
            if "errorCode" in json_content:
                raise OSError("Error: %s" % json_content["errorText"])
            else:
                raise err

        return connections


if __name__ == "__main__":
    """
    Simple test of the rmv api accessor
    """

    api_url = "http://www.rmv.de/hapi/departureBoard?json"
    access_token = "REMOVED"

    test_route_lui_hbf = {"start": "3004736", "end": "3024730"}

    rmv_api = RmvAPIAccessor(api_url, access_token)

    test_result_departures = rmv_api.find_departures(test_route_lui_hbf, None)

    print(test_result_departures)
