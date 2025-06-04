"""
Commande Django pour migrer les métriques existantes vers InfluxDB.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from equipment.models import Equipment
from metrics.models import NetworkMetric
from influxdb_integration.services import EquipmentMetricsService
from datetime import datetime
import time


class Command(BaseCommand):
    help = 'Migre les métriques existantes de Django vers InfluxDB'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Taille des lots pour la migration (défaut: 100)'
        )
        parser.add_argument(
            '--equipment-id',
            type=int,
            help='Migrer seulement un équipement spécifique'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Migrer les métriques des X derniers jours (défaut: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans migration réelle'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forcer la migration même si des données existent déjà'
        )
    
    def handle(self, *args, **options):
        batch_size = options['batch_size']
        equipment_id = options.get('equipment_id')
        days = options['days']
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)
        
        # Filtrer les métriques à migrer
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        queryset = NetworkMetric.objects.filter(timestamp__gte=cutoff_date)
        
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        
        total_metrics = queryset.count()
        
        if total_metrics == 0:
            self.stdout.write(self.style.WARNING('Aucune métrique à migrer'))
            return
        
        self.stdout.write(f'📊 Migration de {total_metrics:,} métriques vers InfluxDB')
        self.stdout.write(f'📅 Période: {days} derniers jours')
        self.stdout.write(f'📦 Taille des lots: {batch_size}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 MODE SIMULATION - Aucune migration réelle'))
        
        # Vérifier si des données existent déjà
        if not force and not dry_run:
            existing_measurements = influxdb_manager.get_measurements()
            if 'equipment_metrics' in existing_measurements:
                confirm = input('\n⚠️  Des données existent déjà dans InfluxDB. Continuer ? (oui/non): ')
                if confirm.lower() not in ['oui', 'yes', 'y', 'o']:
                    self.stdout.write(self.style.WARNING('Migration annulée'))
                    return
        
        # Migration par lots
        migrated_count = 0
        error_count = 0
        start_time = time.time()
        
        try:
            for i in range(0, total_metrics, batch_size):
                batch = queryset[i:i + batch_size]
                batch_data = []
                
                for metric in batch:
                    try:
                        # Convertir la métrique Django en format InfluxDB
                        metric_data = {
                            'equipment_id': metric.equipment_id,
                            'metric_type': self._map_metric_type(metric),
                            'value': self._extract_metric_value(metric),
                            'timestamp': metric.timestamp,
                            'tags': {
                                'source': 'django_migration',
                                'original_id': str(metric.id)
                            },
                            'fields': self._extract_additional_fields(metric)
                        }
                        
                        batch_data.append(metric_data)
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Erreur métrique {metric.id}: {e}'))
                        error_count += 1
                
                # Enregistrer le lot
                if batch_data and not dry_run:
                    try:
                        result = EquipmentMetricsService.bulk_record_metrics(batch_data)
                        migrated_count += result['success']
                        error_count += result['errors']
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Erreur lot {i//batch_size + 1}: {e}'))
                        error_count += len(batch_data)
                elif dry_run:
                    migrated_count += len(batch_data)
                
                # Afficher le progrès
                progress = ((i + batch_size) / total_metrics) * 100
                self.stdout.write(f'🔄 Progrès: {progress:.1f}% ({migrated_count:,}/{total_metrics:,})')
        
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⚠️  Migration interrompue'))
        
        # Résumé
        elapsed_time = time.time() - start_time
        
        if dry_run:
            self.stdout.write(f'\n📊 Simulation terminée:')
        else:
            self.stdout.write(f'\n✅ Migration terminée:')
        
        self.stdout.write(f'   📈 Métriques migrées: {migrated_count:,}')
        self.stdout.write(f'   ❌ Erreurs: {error_count:,}')
        self.stdout.write(f'   ⏱️  Temps: {elapsed_time:.1f}s')
        
        if migrated_count > 0:
            rate = migrated_count / elapsed_time
            self.stdout.write(f'   🚀 Débit: {rate:.1f} métriques/s')
    
    def _map_metric_type(self, metric):
        """Mappe les types de métriques Django vers InfluxDB."""
        # Mapping basé sur les champs disponibles dans NetworkMetric
        if metric.cpu_usage is not None:
            return 'cpu_usage'
        elif metric.memory_usage is not None:
            return 'memory_usage'
        elif metric.network_usage is not None:
            return 'network_usage'
        elif metric.disk_usage is not None:
            return 'disk_usage'
        else:
            return 'general_metric'
    
    def _extract_metric_value(self, metric):
        """Extrait la valeur principale de la métrique."""
        if metric.cpu_usage is not None:
            return float(metric.cpu_usage)
        elif metric.memory_usage is not None:
            return float(metric.memory_usage)
        elif metric.network_usage is not None:
            return float(metric.network_usage)
        elif metric.disk_usage is not None:
            return float(metric.disk_usage)
        else:
            return 0.0
    
    def _extract_additional_fields(self, metric):
        """Extrait les champs supplémentaires."""
        fields = {}
        
        if metric.cpu_usage is not None:
            fields['cpu_usage'] = float(metric.cpu_usage)
        if metric.memory_usage is not None:
            fields['memory_usage'] = float(metric.memory_usage)
        if metric.network_usage is not None:
            fields['network_usage'] = float(metric.network_usage)
        if metric.disk_usage is not None:
            fields['disk_usage'] = float(metric.disk_usage)
        
        return fields