"""
URLs pour l'API InfluxDB.
"""
from django.urls import path
from . import views
from .health_check import influxdb_health_check, influxdb_readiness_check, influxdb_liveness_check

app_name = 'influxdb'

urlpatterns = [
    # Métriques d'équipement
    path('equipment/<int:equipment_id>/metrics/', 
         views.record_equipment_metric, 
         name='record-metric'),
    
    path('equipment/<int:equipment_id>/metrics/get/', 
         views.get_equipment_metrics, 
         name='get-metrics'),
    
    path('equipment/<int:equipment_id>/availability/', 
         views.record_availability_check, 
         name='record-availability'),
    
    path('equipment/<int:equipment_id>/dashboard/', 
         views.get_equipment_dashboard, 
         name='equipment-dashboard'),
    
    path('equipment/<int:equipment_id>/availability-report/', 
         views.generate_availability_report, 
         name='availability-report'),
    
    path('equipment/<int:equipment_id>/alerts/', 
         views.get_equipment_alerts, 
         name='equipment-alerts'),
    
    # Résumé par site
    path('sites/<int:site_id>/equipment-summary/', 
         views.get_site_equipment_summary, 
         name='site-equipment-summary'),
    
    # Dashboard global et administration
    path('dashboard/', 
         views.get_global_dashboard, 
         name='global-dashboard'),
    
    path('status/', 
         views.get_influxdb_status, 
         name='influxdb-status'),
    
    path('schema/', 
         views.get_metrics_schema, 
         name='metrics-schema'),
    
    # Opérations en lot
    path('metrics/bulk/', 
         views.bulk_record_metrics, 
         name='bulk-metrics'),
    
    path('availability/bulk/', 
         views.record_bulk_availability, 
         name='bulk-availability'),
    
    # Maintenance
    path('cleanup/', 
         views.cleanup_old_data, 
         name='cleanup-data'),
    
    # Health checks
    path('health/', 
         influxdb_health_check, 
         name='health-check'),
    
    path('readiness/', 
         influxdb_readiness_check, 
         name='readiness-check'),
    
    path('liveness/', 
         influxdb_liveness_check, 
         name='liveness-check'),
]