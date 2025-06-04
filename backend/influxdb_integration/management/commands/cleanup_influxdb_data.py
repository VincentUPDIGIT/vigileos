"""
Commande Django pour nettoyer les anciennes données InfluxDB.
"""
from django.core.management.base import BaseCommand
from influxdb_integration.client import influxdb_manager
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Nettoie les anciennes données InfluxDB'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--older-than',
            type=int,
            default=30,
            help='Supprimer les données plus anciennes que X jours (défaut: 30)'
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=7,
            help='Garder les X derniers jours (défaut: 7)'
        )
        parser.add_argument(
            '--measurement',
            type=str,
            help='Mesure spécifique à nettoyer (défaut: toutes)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans suppression réelle'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forcer la suppression sans confirmation'
        )
    
    def handle(self, *args, **options):
        older_than = options['older_than']
        keep_days = options['keep_days']
        measurement = options.get('measurement')
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)
        
        if older_than < keep_days:
            self.stdout.write(self.style.ERROR(
                f'Erreur: older-than ({older_than}) doit être >= keep-days ({keep_days})'
            ))
            return
        
        # Calculer les périodes
        start_time = f"-{older_than}d"
        stop_time = f"-{keep_days}d"
        
        # Déterminer les mesures à nettoyer
        if measurement:
            measurements = [measurement]
        else:
            measurements = influxdb_manager.get_measurements()
            if not measurements:
                measurements = ['equipment_metrics', 'equipment_status_changes']
        
        self.stdout.write(f'🧹 Nettoyage des données InfluxDB')
        self.stdout.write(f'📅 Période: plus de {older_than} jours (garder {keep_days} derniers jours)')
        self.stdout.write(f'📊 Mesures: {", ".join(measurements)}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 MODE SIMULATION - Aucune suppression réelle'))
        
        # Confirmation
        if not force and not dry_run:
            confirm = input('\n⚠️  Confirmer la suppression ? (oui/non): ')
            if confirm.lower() not in ['oui', 'yes', 'y', 'o']:
                self.stdout.write(self.style.WARNING('Opération annulée'))
                return
        
        # Nettoyer chaque mesure
        total_cleaned = 0
        
        for measurement_name in measurements:
            try:
                self.stdout.write(f'\n🔄 Traitement de {measurement_name}...')
                
                if dry_run:
                    # En mode simulation, juste afficher ce qui serait supprimé
                    query = f'''
                    from(bucket: "{influxdb_manager.bucket}")
                        |> range(start: {start_time}, stop: {stop_time})
                        |> filter(fn: (r) => r["_measurement"] == "{measurement_name}")
                        |> count()
                    '''
                    
                    result = influxdb_manager.query_raw(query)
                    if result:
                        count = sum(point.get('value', 0) for point in result)
                        self.stdout.write(f'   📊 {count:,} points seraient supprimés')
                        total_cleaned += count
                    else:
                        self.stdout.write(f'   ✅ Aucune donnée à supprimer')
                else:
                    # Suppression réelle
                    success = influxdb_manager.delete_measurement(
                        measurement=measurement_name,
                        start=start_time,
                        stop=stop_time
                    )
                    
                    if success:
                        self.stdout.write(self.style.SUCCESS(f'   ✅ {measurement_name} nettoyé'))
                        total_cleaned += 1
                    else:
                        self.stdout.write(self.style.ERROR(f'   ❌ Erreur lors du nettoyage de {measurement_name}'))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Erreur: {e}'))
        
        # Résumé
        if dry_run:
            self.stdout.write(f'\n📊 Simulation terminée: {total_cleaned:,} points seraient supprimés')
        else:
            self.stdout.write(f'\n✅ Nettoyage terminé: {total_cleaned} mesures traitées')
            
            # Vérifier la taille après nettoyage
            db_size = influxdb_manager.get_database_size()
            if db_size:
                self.stdout.write(f'💾 Points restants: {db_size.get("total_points", 0):,}')