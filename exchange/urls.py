# exchange/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('timeseries/', views.TimeSeriesView.as_view(), name='time_series'),
    path('currencies/', views.CurrenciesView.as_view(), name='currencies'),
]