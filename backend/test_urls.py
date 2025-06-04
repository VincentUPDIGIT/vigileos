#!/usr/bin/env python
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vigileos.settings.test')
django.setup()

from django.urls import reverse
from django.conf import settings

print("Apps installées:", settings.INSTALLED_APPS)
print("\nTest des URLs InfluxDB:")

try:
    url = reverse('influxdb:influxdb-status')
    print(f"URL status: {url}")
except Exception as e:
    print(f"Erreur URL status: {e}")

try:
    url = reverse('influxdb:global-dashboard')
    print(f"URL dashboard: {url}")
except Exception as e:
    print(f"Erreur URL dashboard: {e}")