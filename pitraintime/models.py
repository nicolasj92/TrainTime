from datetime import datetime

from django.db import models
from django.utils import timezone
from django.utils.timesince import timesince


class Station(models.Model):
    hafas_id = models.CharField(max_length=7)
    name = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Connection(models.Model):
    station_start = models.ForeignKey(
        Station, on_delete=models.CASCADE, related_name="station_id_start"
    )
    station_end = models.ForeignKey(
        Station, on_delete=models.CASCADE, related_name="station_id_end"
    )
    time_at_start = models.DateTimeField()
    line_name = models.CharField(max_length=100)
    line_direction = models.CharField(max_length=100)
    vehicle_type = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)

    def get_timediff_from_now_min(self):
        now = timezone.make_aware(datetime.now(), timezone.get_current_timezone())
        return timesince(now, self.time_at_start)
