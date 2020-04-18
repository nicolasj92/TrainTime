from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings

from pitraintime.models import Connection, Station
from pitraintime.management.commands._api import RmvAPIAccessor
from pitraintime.utils.config import TrainTimeConfig


class Command(BaseCommand):
    help = "Call the API to get the latest departures for the configured routes and write them into the database."

    @staticmethod
    def _cleanup_connections():
        Connection.objects.all().delete()

    def handle(self, *args, **options):
        # Initialize config and api accessor
        config = TrainTimeConfig()
        api_accessor = RmvAPIAccessor(
            api_url=settings.RMV_API_URL, access_token=settings.RMV_ACCESS_TOKEN
        )

        connections = []

        # Query all routes
        for route in config.routes:
            connections += api_accessor.find_departures(
                route=route, max_departures=config.max_departures
            )

        # Truncate connections DB
        self._cleanup_connections()

        # Write all connections in the database
        for connection in connections:
            Connection.objects.create(
                station_start=Station.objects.get(hafas_id=connection.station_id_start),
                station_end=Station.objects.get(hafas_id=connection.station_id_end),
                line_name=connection.line_name,
                line_direction=connection.line_direction,
                vehicle_type=connection.vehicle_type,
                time_at_start=timezone.make_aware(
                    connection.time_at_start, timezone.get_current_timezone()
                ),
            )

        print(
            "Got {} connections at {}!".format(
                len(connections), datetime.now().strftime("%H:%M")
            )
        )
