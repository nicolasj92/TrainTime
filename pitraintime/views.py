from datetime import datetime

from django.shortcuts import render
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.urls import reverse

from pitraintime.models import Connection, Station
from pitraintime.forms import RouteSettingsForm
from pitraintime.utils.config import TrainTimeConfig

# Create your views here.
def train_times(request):
    # TODO can this go into models.py?
    # TODO maybe not the best idea to always load the json file again
    config = TrainTimeConfig()
    # TODO make parameter
    num_entries = 5

    start_stations = []
    end_stations = []
    route_connections = []

    for route in config.routes:

        # Get the next num_entries upcoming connection
        connections = Connection.objects.filter(
            time_at_start__gte=timezone.make_aware(
                datetime.now(), timezone.get_current_timezone()
            ),
            station_start__hafas_id=route["start"],
            station_end__hafas_id=route["end"],
        ).order_by("time_at_start")[:num_entries]

        start_station = Station.objects.filter(hafas_id=route["start"])[0]
        end_station = Station.objects.filter(hafas_id=route["end"])[0]

        route_connections.append(connections)
        start_stations.append(start_station)
        end_stations.append(end_station)

    route_information = zip(start_stations, end_stations, route_connections)

    context = {"route_information": route_information, "page_train_times": "active"}
    # context = {"connections": Connection.objects.all(), "page_train_times": "active"}

    return render(request, "train_times.html", context)


def settings(request):
    stations = Station.objects.all()
    config = TrainTimeConfig()
    context = {"stations": stations, "config": config, "page_settings": "active"}
    return render(request, "settings.html", context)


def save_route_settings(request):
    config = TrainTimeConfig()
    if request.method == "POST":
        form = RouteSettingsForm(request.POST)

        if form.is_valid():
            config.set_route(
                0,
                form.cleaned_data["route_0_start_id"],
                form.cleaned_data["route_0_end_id"],
            )
            config.set_route(
                1,
                form.cleaned_data["route_1_start_id"],
                form.cleaned_data["route_1_end_id"],
            )
            config.save()
            return HttpResponseRedirect(reverse("settings/save_route_settings"))
        else:
            raise Exception(form.errors)
    else:
        form = RouteSettingsForm(
            initial={
                "route_0_start_id": config.routes[0]["start"],
                "route_0_end_id": config.routes[0]["end"],
                "route_1_start_id": config.routes[1]["start"],
                "route_1_ends_id": config.routes[1]["end"],
            }
        )
        context = {"form": form}
        return render(request, "settings.html", context)


def about(request):
    context = {"page_about": "active"}
    return render(request, "about.html", context)

