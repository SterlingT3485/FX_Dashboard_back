from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('api/', include('exchange.urls')),  # include exchange app's URLs
]