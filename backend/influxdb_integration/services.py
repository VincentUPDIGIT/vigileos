"""
Services pour l'intégration des équipements avec InfluxDB.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from equipment.models import Equipment
from .client import influxdb_manager
import logging
import random
import json

logger = logging.getLogger(__name__)


class EquipmentMetricsService:
    """Service pour gérer les métriques des équipements."""
    
    @staticmethod
    def record_equipment_metric(equipment: Equipment, metric_name: str, value: float, 
                              additional_fields: Optional[Dict] = None):
        """
        Enregistre une métrique pour un équipement.
        
        Args:
            equipment: Instance de l'équipement
            metric_name: Nom de la métrique
            value: Valeur de la métrique
            additional_fields: Champs supplémentaires
        """
        tags = {
            'site_id': str(equipment.site_id),
            'site_name': equipment.site.name,
            'equipment_type': equipment.type,
            'equipment_name': equipment.name
        }
        
        if equipment.ip_address:
            tags['ip_address'] = equipment.ip_address
        
        influxdb_manager.write_equipment_metric(
            equipment_id=equipment.id,
            metric_name=metric_name,
            value=value,
            tags=tags,
            fields=additional_fields
        )
    
    @staticmethod
    def record_availability_check(equipment: Equipment, is_available: bool, 
                                response_time: Optional[float] = None):
        """
        Enregistre un contrôle de disponibilité.
        
        Args:
            equipment: Instance de l'équipement
            is_available: Si l'équipement est disponible
            response_time: Temps de réponse en ms
        """
        value = 1.0 if is_available else 0.0
        fields = {}
        
        if response_time is not None:
            fields['response_time_ms'] = response_time
        
        EquipmentMetricsService.record_equipment_metric(
            equipment=equipment,
            metric_name='availability',
            value=value,
            additional_fields=fields
        )
    
    @staticmethod
    def record_performance_metrics(equipment: Equipment, metrics: Dict[str, float]):
        """
        Enregistre plusieurs métriques de performance.
        
        Args:
            equipment: Instance de l'équipement
            metrics: Dictionnaire des métriques {nom: valeur}
        """
        for metric_name, value in metrics.items():
            EquipmentMetricsService.record_equipment_metric(
                equipment=equipment,
                metric_name=metric_name,
                value=value
            )
    
    @staticmethod
    def simulate_equipment_metrics(equipment: Equipment):
        """
        Simule des métriques pour un équipement (pour les tests).
        
        Args:
            equipment: Instance de l'équipement
        """
        # Disponibilité
        is_online = equipment.status == 'online'
        availability = 1.0 if is_online else 0.0
        response_time = random.uniform(10, 100) if is_online else None
        
        EquipmentMetricsService.record_availability_check(
            equipment=equipment,
            is_available=is_online,
            response_time=response_time
        )
        
        # Métriques spécifiques par type d'équipement
        if equipment.type == 'camera':
            metrics = {
                'fps': random.uniform(20, 30) if is_online else 0,
                'bitrate_mbps': random.uniform(2, 8) if is_online else 0,
                'packet_loss': random.uniform(0, 0.5) if is_online else 100
            }
        elif equipment.type == 'server':
            metrics = {
                'cpu_usage': random.uniform(10, 80) if is_online else 0,
                'memory_usage': random.uniform(30, 90) if is_online else 0,
                'disk_usage': random.uniform(20, 85) if is_online else 0,
                'temperature': random.uniform(40, 70) if is_online else 0
            }
        elif equipment.type == 'switch':
            metrics = {
                'bandwidth_usage': random.uniform(100, 1000) if is_online else 0,
                'port_errors': random.randint(0, 5) if is_online else 0,
                'uptime_hours': random.randint(100, 8760) if is_online else 0
            }
        else:
            metrics = {
                'health_score': random.uniform(70, 100) if is_online else 0
            }
        
        EquipmentMetricsService.record_performance_metrics(equipment, metrics)
    
    @staticmethod
    def record_metric(equipment_id: int, metric_type: str, value: float, 
                     tags: Optional[Dict[str, str]] = None, 
                     fields: Optional[Dict[str, Any]] = None,
                     timestamp: Optional[datetime] = None):
        """
        Enregistre une métrique générique.
        
        Args:
            equipment_id: ID de l'équipement
            metric_type: Type de métrique
            value: Valeur principale
            tags: Tags supplémentaires
            fields: Champs supplémentaires
            timestamp: Timestamp (par défaut: maintenant)
        """
        try:
            equipment = Equipment.objects.get(id=equipment_id)
            
            # Tags de base
            base_tags = {
                'site_id': str(equipment.site_id),
                'site_name': equipment.site.name,
                'equipment_type': equipment.type,
                'equipment_name': equipment.name
            }
            
            if equipment.ip_address:
                base_tags['ip_address'] = equipment.ip_address
            
            # Fusionner avec les tags supplémentaires
            if tags:
                base_tags.update(tags)
            
            influxdb_manager.write_equipment_metric(
                equipment_id=equipment_id,
                metric_name=metric_type,
                value=value,
                tags=base_tags,
                fields=fields,
                timestamp=timestamp
            )
            
        except Equipment.DoesNotExist:
            logger.error(f"Équipement {equipment_id} non trouvé")
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de métrique: {e}")
    
    @staticmethod
    def record_availability(equipment_id: int, is_available: bool, 
                          reason: Optional[str] = None,
                          response_time: Optional[float] = None):
        """
        Enregistre la disponibilité d'un équipement.
        
        Args:
            equipment_id: ID de l'équipement
            is_available: Si l'équipement est disponible
            reason: Raison de l'état
            response_time: Temps de réponse en ms
        """
        tags = {}
        if reason:
            tags['reason'] = reason
        
        fields = {}
        if response_time is not None:
            fields['response_time_ms'] = response_time
        
        EquipmentMetricsService.record_metric(
            equipment_id=equipment_id,
            metric_type='availability',
            value=1.0 if is_available else 0.0,
            tags=tags,
            fields=fields
        )
    
    @staticmethod
    def record_performance(equipment_id: int, cpu_usage: Optional[float] = None,
                         memory_usage: Optional[float] = None,
                         response_time: Optional[float] = None,
                         additional_metrics: Optional[Dict[str, float]] = None):
        """
        Enregistre les métriques de performance.
        
        Args:
            equipment_id: ID de l'équipement
            cpu_usage: Utilisation CPU en %
            memory_usage: Utilisation mémoire en %
            response_time: Temps de réponse en ms
            additional_metrics: Métriques supplémentaires
        """
        if cpu_usage is not None:
            EquipmentMetricsService.record_metric(
                equipment_id=equipment_id,
                metric_type='cpu_usage',
                value=cpu_usage
            )
        
        if memory_usage is not None:
            EquipmentMetricsService.record_metric(
                equipment_id=equipment_id,
                metric_type='memory_usage',
                value=memory_usage
            )
        
        if response_time is not None:
            EquipmentMetricsService.record_metric(
                equipment_id=equipment_id,
                metric_type='response_time',
                value=response_time
            )
        
        if additional_metrics:
            for metric_name, value in additional_metrics.items():
                EquipmentMetricsService.record_metric(
                    equipment_id=equipment_id,
                    metric_type=metric_name,
                    value=value
                )
    
    @staticmethod
    def bulk_record_metrics(metrics_data: List[Dict]) -> Dict[str, int]:
        """
        Enregistre plusieurs métriques en lot.
        
        Args:
            metrics_data: Liste de dictionnaires avec les données de métriques
        
        Returns:
            Statistiques d'enregistrement
        """
        from influxdb_client import Point
        
        points = []
        success_count = 0
        error_count = 0
        
        for metric in metrics_data:
            try:
                equipment_id = metric['equipment_id']
                equipment = Equipment.objects.get(id=equipment_id)
                
                point = Point("equipment_metrics") \
                    .tag("equipment_id", str(equipment_id)) \
                    .tag("metric_name", metric['metric_type']) \
                    .tag("site_id", str(equipment.site_id)) \
                    .tag("site_name", equipment.site.name) \
                    .tag("equipment_type", equipment.type) \
                    .tag("equipment_name", equipment.name)
                
                if equipment.ip_address:
                    point = point.tag("ip_address", equipment.ip_address)
                
                # Ajouter tags supplémentaires
                if 'tags' in metric:
                    for key, val in metric['tags'].items():
                        point = point.tag(key, str(val))
                
                # Ajouter la valeur principale
                point = point.field("value", float(metric['value']))
                
                # Ajouter champs supplémentaires
                if 'fields' in metric:
                    for key, val in metric['fields'].items():
                        point = point.field(key, val)
                
                # Timestamp
                if 'timestamp' in metric:
                    point = point.time(metric['timestamp'])
                
                points.append(point)
                success_count += 1
                
            except Exception as e:
                logger.error(f"Erreur lors de la préparation du point: {e}")
                error_count += 1
        
        # Écrire en lot
        if points:
            try:
                influxdb_manager.write_points_batch(points)
                logger.info(f"Batch de {len(points)} métriques écrit avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de l'écriture en lot: {e}")
                error_count += len(points)
                success_count = 0
        
        return {
            'success': success_count,
            'errors': error_count,
            'total': len(metrics_data)
        }


class EquipmentAnalyticsService:
    """Service pour l'analyse des données d'équipement."""
    
    @staticmethod
    def get_equipment_dashboard_data(equipment_id: int, period: str = "24h") -> Dict:
        """
        Récupère les données pour le tableau de bord d'un équipement.
        
        Args:
            equipment_id: ID de l'équipement
            period: Période d'analyse (24h, 7d, 30d)
        
        Returns:
            Données du tableau de bord
        """
        start = f"-{period}"
        
        # Statistiques générales
        stats = influxdb_manager.get_equipment_statistics(equipment_id, start)
        
        # Métriques de disponibilité
        availability_data = influxdb_manager.query_equipment_metrics(
            equipment_id=equipment_id,
            metric_name='availability',
            start=start,
            aggregation='mean'
        )
        
        # Temps de réponse moyen
        response_time_data = influxdb_manager.query_equipment_metrics(
            equipment_id=equipment_id,
            metric_name='response_time_ms',
            start=start,
            aggregation='mean'
        )
        
        return {
            'statistics': stats,
            'availability_trend': availability_data,
            'response_time_trend': response_time_data,
            'period': period
        }
    
    @staticmethod
    def get_site_equipment_summary(site_id: int, period: str = "24h") -> Dict:
        """
        Récupère un résumé des équipements d'un site.
        
        Args:
            site_id: ID du site
            period: Période d'analyse
        
        Returns:
            Résumé des équipements du site
        """
        from equipment.models import Equipment
        
        equipments = Equipment.objects.filter(site_id=site_id)
        summary = {
            'total_equipment': equipments.count(),
            'online': 0,
            'offline': 0,
            'warning': 0,
            'average_availability': 0,
            'equipment_details': []
        }
        
        total_availability = 0
        
        for equipment in equipments:
            availability = influxdb_manager.calculate_equipment_availability(
                equipment_id=equipment.id,
                start=f"-{period}"
            )
            
            total_availability += availability
            
            # Compter par statut
            if equipment.status == 'online':
                summary['online'] += 1
            elif equipment.status == 'offline':
                summary['offline'] += 1
            else:
                summary['warning'] += 1
            
            summary['equipment_details'].append({
                'id': equipment.id,
                'name': equipment.name,
                'type': equipment.type,
                'status': equipment.status,
                'availability': availability
            })
        
        if equipments.count() > 0:
            summary['average_availability'] = round(total_availability / equipments.count(), 2)
        
        return summary
    
    @staticmethod
    def generate_availability_report(equipment_id: int, start_date: datetime, 
                                   end_date: datetime) -> Dict:
        """
        Génère un rapport de disponibilité détaillé.
        
        Args:
            equipment_id: ID de l'équipement
            start_date: Date de début
            end_date: Date de fin
        
        Returns:
            Rapport de disponibilité
        """
        start = start_date.isoformat() + "Z"
        stop = end_date.isoformat() + "Z"
        
        # Disponibilité globale
        overall_availability = influxdb_manager.calculate_equipment_availability(
            equipment_id=equipment_id,
            start=start,
            stop=stop
        )
        
        # Données horaires
        hourly_data = influxdb_manager.query_equipment_metrics(
            equipment_id=equipment_id,
            metric_name='availability',
            start=start,
            stop=stop,
            aggregation='mean'
        )
        
        # Calcul des périodes d'indisponibilité
        downtime_periods = []
        current_downtime = None
        
        for point in hourly_data:
            if point['value'] < 0.5:  # Considéré comme indisponible
                if not current_downtime:
                    current_downtime = {
                        'start': point['time'],
                        'end': point['time'],
                        'duration_hours': 1
                    }
                else:
                    current_downtime['end'] = point['time']
                    current_downtime['duration_hours'] += 1
            else:
                if current_downtime:
                    downtime_periods.append(current_downtime)
                    current_downtime = None
        
        if current_downtime:
            downtime_periods.append(current_downtime)
        
        total_hours = (end_date - start_date).total_seconds() / 3600
        total_downtime_hours = sum(p['duration_hours'] for p in downtime_periods)
        
        return {
            'equipment_id': equipment_id,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'total_hours': total_hours
            },
            'availability': {
                'percentage': overall_availability,
                'uptime_hours': total_hours - total_downtime_hours,
                'downtime_hours': total_downtime_hours
            },
            'downtime_periods': downtime_periods,
            'hourly_data': hourly_data
        }
    
    @staticmethod
    def get_equipment_metrics(equipment_id: int, start_time: datetime, 
                            end_time: datetime, metric_types: Optional[List[str]] = None) -> Dict:
        """
        Récupère les métriques d'un équipement sur une période.
        
        Args:
            equipment_id: ID de l'équipement
            start_time: Date de début
            end_time: Date de fin
            metric_types: Types de métriques à récupérer
        
        Returns:
            Données des métriques
        """
        start = start_time.isoformat() + "Z"
        stop = end_time.isoformat() + "Z"
        
        if not metric_types:
            metric_types = ['availability', 'cpu_usage', 'memory_usage', 'response_time']
        
        metrics_data = {}
        
        for metric_type in metric_types:
            try:
                data = influxdb_manager.query_equipment_metrics(
                    equipment_id=equipment_id,
                    metric_name=metric_type,
                    start=start,
                    stop=stop
                )
                metrics_data[metric_type] = data
            except Exception as e:
                logger.error(f"Erreur lors de la récupération de {metric_type}: {e}")
                metrics_data[metric_type] = []
        
        return {
            'equipment_id': equipment_id,
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'metrics': metrics_data
        }
    
    @staticmethod
    def calculate_availability(equipment_id: int, start_time: datetime, 
                             end_time: datetime) -> float:
        """
        Calcule le taux de disponibilité sur une période.
        
        Args:
            equipment_id: ID de l'équipement
            start_time: Date de début
            end_time: Date de fin
        
        Returns:
            Taux de disponibilité en pourcentage
        """
        start = start_time.isoformat() + "Z"
        stop = end_time.isoformat() + "Z"
        
        return influxdb_manager.calculate_equipment_availability(
            equipment_id=equipment_id,
            start=start,
            stop=stop
        )
    
    @staticmethod
    def get_performance_stats(equipment_id: int, start_time: datetime, 
                            end_time: datetime) -> Dict:
        """
        Calcule les statistiques de performance.
        
        Args:
            equipment_id: ID de l'équipement
            start_time: Date de début
            end_time: Date de fin
        
        Returns:
            Statistiques de performance
        """
        start = start_time.isoformat() + "Z"
        stop = end_time.isoformat() + "Z"
        
        stats = {}
        
        # Métriques à analyser
        metrics = ['cpu_usage', 'memory_usage', 'response_time']
        
        for metric in metrics:
            try:
                # Moyenne
                avg_data = influxdb_manager.query_equipment_metrics(
                    equipment_id=equipment_id,
                    metric_name=metric,
                    start=start,
                    stop=stop,
                    aggregation='mean'
                )
                
                # Maximum
                max_data = influxdb_manager.query_equipment_metrics(
                    equipment_id=equipment_id,
                    metric_name=metric,
                    start=start,
                    stop=stop,
                    aggregation='max'
                )
                
                # Minimum
                min_data = influxdb_manager.query_equipment_metrics(
                    equipment_id=equipment_id,
                    metric_name=metric,
                    start=start,
                    stop=stop,
                    aggregation='min'
                )
                
                if avg_data:
                    avg_value = sum(point['value'] for point in avg_data) / len(avg_data)
                    max_value = max(point['value'] for point in max_data) if max_data else 0
                    min_value = min(point['value'] for point in min_data) if min_data else 0
                    
                    stats[f'{metric}_avg'] = round(avg_value, 2)
                    stats[f'{metric}_max'] = round(max_value, 2)
                    stats[f'{metric}_min'] = round(min_value, 2)
                else:
                    stats[f'{metric}_avg'] = 0
                    stats[f'{metric}_max'] = 0
                    stats[f'{metric}_min'] = 0
                    
            except Exception as e:
                logger.error(f"Erreur lors du calcul des stats pour {metric}: {e}")
                stats[f'{metric}_avg'] = 0
                stats[f'{metric}_max'] = 0
                stats[f'{metric}_min'] = 0
        
        return stats
    
    @staticmethod
    def get_global_dashboard_data(hours: int = 24) -> Dict:
        """
        Récupère les données pour le dashboard global.
        
        Args:
            hours: Nombre d'heures à analyser
        
        Returns:
            Données du dashboard global
        """
        cache_key = f'influxdb_dashboard_{hours}h'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        from sites.models import Site
        
        # Récupérer tous les équipements
        equipments = Equipment.objects.select_related('site').all()
        
        # Statistiques générales
        total_equipment = equipments.count()
        online_count = equipments.filter(status='online').count()
        offline_count = equipments.filter(status='offline').count()
        warning_count = equipments.filter(status='warning').count()
        
        # Calculer la disponibilité moyenne
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        total_availability = 0
        equipment_details = []
        
        for equipment in equipments[:50]:  # Limiter pour les performances
            try:
                availability = EquipmentAnalyticsService.calculate_availability(
                    equipment_id=equipment.id,
                    start_time=start_time,
                    end_time=end_time
                )
                
                total_availability += availability
                
                # Dernières métriques
                latest_metrics = influxdb_manager.query_equipment_metrics(
                    equipment_id=equipment.id,
                    metric_name='availability',
                    start='-1h',
                    stop='now'
                )
                
                last_seen = None
                if latest_metrics:
                    last_seen = latest_metrics[-1]['time']
                
                equipment_details.append({
                    'id': equipment.id,
                    'name': equipment.name,
                    'type': equipment.type,
                    'status': equipment.status,
                    'site_name': equipment.site.name,
                    'availability': availability,
                    'last_seen': last_seen
                })
                
            except Exception as e:
                logger.error(f"Erreur pour équipement {equipment.id}: {e}")
        
        avg_availability = total_availability / total_equipment if total_equipment > 0 else 0
        
        # Statistiques par site
        sites_stats = []
        for site in Site.objects.all():
            site_summary = EquipmentAnalyticsService.get_site_equipment_summary(
                site_id=site.id,
                period=f'{hours}h'
            )
            sites_stats.append({
                'site_id': site.id,
                'site_name': site.name,
                'summary': site_summary
            })
        
        dashboard_data = {
            'summary': {
                'total_equipment': total_equipment,
                'online': online_count,
                'offline': offline_count,
                'warning': warning_count,
                'average_availability': round(avg_availability, 2),
                'period_hours': hours
            },
            'equipment_details': equipment_details,
            'sites_stats': sites_stats,
            'last_updated': datetime.now().isoformat()
        }
        
        # Cache pour 5 minutes
        cache.set(cache_key, dashboard_data, 300)
        
        return dashboard_data
    
    @staticmethod
    def get_alerts_from_metrics(equipment_id: int, hours: int = 24) -> List[Dict]:
        """
        Génère des alertes basées sur les métriques.
        
        Args:
            equipment_id: ID de l'équipement
            hours: Période d'analyse en heures
        
        Returns:
            Liste des alertes détectées
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        alerts = []
        
        # Seuils d'alerte
        thresholds = {
            'cpu_usage': {'warning': 80, 'critical': 95},
            'memory_usage': {'warning': 85, 'critical': 95},
            'response_time': {'warning': 1000, 'critical': 5000},  # ms
            'availability': {'warning': 95, 'critical': 90}  # %
        }
        
        for metric_type, threshold in thresholds.items():
            try:
                stats = EquipmentAnalyticsService.get_performance_stats(
                    equipment_id=equipment_id,
                    start_time=start_time,
                    end_time=end_time
                )
                
                if metric_type == 'availability':
                    current_value = EquipmentAnalyticsService.calculate_availability(
                        equipment_id=equipment_id,
                        start_time=start_time,
                        end_time=end_time
                    )
                else:
                    current_value = stats.get(f'{metric_type}_avg', 0)
                
                # Vérifier les seuils
                if current_value >= threshold['critical']:
                    alerts.append({
                        'equipment_id': equipment_id,
                        'metric_type': metric_type,
                        'severity': 'critical',
                        'current_value': current_value,
                        'threshold': threshold['critical'],
                        'message': f'{metric_type} critique: {current_value}'
                    })
                elif current_value >= threshold['warning']:
                    alerts.append({
                        'equipment_id': equipment_id,
                        'metric_type': metric_type,
                        'severity': 'warning',
                        'current_value': current_value,
                        'threshold': threshold['warning'],
                        'message': f'{metric_type} élevé: {current_value}'
                    })
                    
            except Exception as e:
                logger.error(f"Erreur lors de l'analyse de {metric_type}: {e}")
        
        return alerts


# Signaux Django pour enregistrer automatiquement les changements de statut
@receiver(pre_save, sender=Equipment)
def track_status_change(sender, instance, **kwargs):
    """Enregistre les changements de statut avant la sauvegarde."""
    if instance.pk:
        try:
            old_instance = Equipment.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Stocker l'ancien statut pour l'utiliser dans post_save
                instance._old_status = old_instance.status
        except Equipment.DoesNotExist:
            pass


@receiver(post_save, sender=Equipment)
def record_status_change(sender, instance, created, **kwargs):
    """Enregistre le changement de statut dans InfluxDB."""
    # Éviter les connexions InfluxDB pendant les tests
    from django.conf import settings
    if hasattr(settings, 'TESTING') and settings.TESTING:
        return
    
    try:
        influxdb_manager = InfluxDBManager()
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation d'InfluxDB: {e}")
        return
    
    if hasattr(instance, '_old_status'):
        tags = {
            'site_id': str(instance.site_id),
            'site_name': instance.site.name,
            'equipment_type': instance.type,
            'equipment_name': instance.name
        }
        
        influxdb_manager.write_equipment_status_change(
            equipment_id=instance.id,
            old_status=instance._old_status,
            new_status=instance.status,
            tags=tags
        )
        
        # Nettoyer l'attribut temporaire
        delattr(instance, '_old_status')
    
    elif created:
        # Nouvel équipement, enregistrer le statut initial
        tags = {
            'site_id': str(instance.site_id),
            'site_name': instance.site.name,
            'equipment_type': instance.type,
            'equipment_name': instance.name
        }
        
        influxdb_manager.write_equipment_status_change(
            equipment_id=instance.id,
            old_status='new',
            new_status=instance.status,
            tags=tags
        )