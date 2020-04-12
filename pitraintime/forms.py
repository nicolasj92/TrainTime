from django_select2.forms import ModelSelect2Widget

from django import forms
from django.core.exceptions import ValidationError

from pitraintime.models import Station


class RouteSelect2Widget(ModelSelect2Widget):
    model = Station
    search_fields = ["name__icontains"]


class RouteSettingsForm(forms.Form):
    route_0_start_id = forms.CharField(widget=RouteSelect2Widget, required=True)
    route_0_end_id = forms.CharField(widget=RouteSelect2Widget, required=True)
    route_1_start_id = forms.CharField(widget=RouteSelect2Widget, required=True)
    route_1_end_id = forms.CharField(widget=RouteSelect2Widget, required=True)
