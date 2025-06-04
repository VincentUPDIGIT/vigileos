"""
Commande Django pour vérifier le statut d'InfluxDB.
"""
from django.core.management.base import BaseCommand
from influxdb_integration.client import influxdb_manager
import json


class Command(BaseCommand):
    help = 'Vérifie le statut de la connexion InfluxDB'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='Sortie au format JSON'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affichage détaillé'
        )
    
    def handle(self, *args, **options):
        json_output = options.get('json', False)
        verbose = options.get('verbose', False)
        
        try:
            # Test de connexion
            is_connected = influxdb_manager.test_connection()
            
            # Informations du bucket
            bucket_info = influxdb_manager.get_bucket_info()
            
            # Mesures disponibles
            measurements = influxdb_manager.get_measurements()
            
            # Taille de la base
            db_size = influxdb_manager.get_database_size()
            
            status_data = {
                'connection': 'OK' if is_connected else 'FAILED',
                'connected': is_connected,
                'bucket': {
                    'name': influxdb_manager.bucket,
                    'exists': bucket_info is not None,
                    'info': bucket_info
                },
                'measurements': {
                    'count': len(measurements),
                    'list': measurements
                },
                'database_size': db_size,
                'config': {
                    'url': influxdb_manager.url,
                    'org': influxdb_manager.org,
                    'bucket': influxdb_manager.bucket
                }
            }
            
            if json_output:
                self.stdout.write(json.dumps(status_data, indent=2, default=str))
            else:
                # Affichage formaté
                if is_connected:
                    self.stdout.write(self.style.SUCCESS('✅ InfluxDB: CONNECTÉ'))
                else:
                    self.stdout.write(self.style.ERROR('❌ InfluxDB: DÉCONNECTÉ'))
                
                self.stdout.write(f'📍 URL: {influxdb_manager.url}')
                self.stdout.write(f'🏢 Organisation: {influxdb_manager.org}')
                self.stdout.write(f'🪣 Bucket: {influxdb_manager.bucket}')
                
                if bucket_info:
                    self.stdout.write(self.style.SUCCESS(f'✅ Bucket existe'))
                    if verbose:
                        self.stdout.write(f'   ID: {bucket_info.get("id")}')
                        self.stdout.write(f'   Créé: {bucket_info.get("created_at")}')
                else:
                    self.stdout.write(self.style.WARNING('⚠️  Bucket non trouvé'))
                
                self.stdout.write(f'📊 Mesures: {len(measurements)}')
                if verbose and measurements:
                    for measurement in measurements:
                        self.stdout.write(f'   - {measurement}')
                
                if db_size:
                    self.stdout.write(f'💾 Points de données: {db_size.get("total_points", 0):,}')
        
        except Exception as e:
            error_data = {
                'connection': 'ERROR',
                'error': str(e)
            }
            
            if json_output:
                self.stdout.write(json.dumps(error_data, indent=2))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Erreur: {e}'))