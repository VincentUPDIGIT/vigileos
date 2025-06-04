"""
Client InfluxDB pour la gestion de la connexion et des opérations de base.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError
from django.conf import settings
import logging
import time

logger = logging.getLogger(__name__)


class InfluxDBManager:
    """Gestionnaire pour les opérations InfluxDB."""
    
    def __init__(self):
        """Initialise la connexion à InfluxDB."""
        self.url = getattr(settings, 'INFLUXDB_URL', os.environ.get('INFLUXDB_URL', 'http://influxdb:8086'))
        self.token = getattr(settings, 'INFLUXDB_TOKEN', os.environ.get('INFLUXDB_TOKEN', ''))
        self.org = getattr(settings, 'INFLUXDB_ORG', os.environ.get('INFLUXDB_ORG', 'vigileos'))
        self.bucket = getattr(settings, 'INFLUXDB_BUCKET', os.environ.get('INFLUXDB_BUCKET', 'equipment_metrics'))
        
        self.client = None
        self.write_api = None
        self.query_api = None
        
        if self.token:
            self._connect()
    
    def _connect(self):
        """Établit la connexion avec InfluxDB."""
        try:
            self.client = InfluxDBClient(
                url=self.url,
                token=self.token,
                org=self.org
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.client.query_api()
            logger.info(f"Connexion établie avec InfluxDB à {self.url}")
        except Exception as e:
            logger.error(f"Erreur de connexion à InfluxDB: {e}")
            raise
    
    def write_equipment_metric(self, equipment_id: int, metric_name: str, value: float, 
                             tags: Optional[Dict[str, str]] = None, 
                             fields: Optional[Dict[str, Any]] = None,
                             timestamp: Optional[datetime] = None):
        """
        Écrit une métrique d'équipement dans InfluxDB.
        
        Args:
            equipment_id: ID de l'équipement
            metric_name: Nom de la métrique (ex: 'availability', 'cpu_usage', 'temperature')
            value: Valeur de la métrique
            tags: Tags supplémentaires (ex: {'site': 'Paris', 'type': 'camera'})
            fields: Champs supplémentaires
            timestamp: Timestamp de la métrique (par défaut: maintenant)
        """
        if not self.write_api:
            logger.warning("InfluxDB non configuré, métrique non enregistrée")
            return
        
        try:
            point = Point("equipment_metrics") \
                .tag("equipment_id", str(equipment_id)) \
                .tag("metric_name", metric_name)
            
            if tags:
                for key, val in tags.items():
                    point = point.tag(key, str(val))
            
            point = point.field("value", float(value))
            
            if fields:
                for key, val in fields.items():
                    point = point.field(key, val)
            
            if timestamp:
                point = point.time(timestamp, WritePrecision.NS)
            
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug(f"Métrique écrite: {metric_name}={value} pour equipment_id={equipment_id}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture de la métrique: {e}")
            raise
    
    def write_equipment_status_change(self, equipment_id: int, old_status: str, 
                                    new_status: str, tags: Optional[Dict[str, str]] = None):
        """
        Enregistre un changement de statut d'équipement.
        
        Args:
            equipment_id: ID de l'équipement
            old_status: Ancien statut
            new_status: Nouveau statut
            tags: Tags supplémentaires
        """
        try:
            point = Point("equipment_status_changes") \
                .tag("equipment_id", str(equipment_id)) \
                .tag("old_status", old_status) \
                .tag("new_status", new_status)
            
            if tags:
                for key, val in tags.items():
                    point = point.tag(key, str(val))
            
            # Valeur numérique pour faciliter les calculs
            status_values = {'online': 1, 'offline': 0, 'warning': 0.5}
            point = point.field("status_value", status_values.get(new_status, -1))
            point = point.field("change_event", 1)
            
            self.write_api.write(bucket=self.bucket, record=point)
            logger.info(f"Changement de statut enregistré: {equipment_id} {old_status} -> {new_status}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du changement de statut: {e}")
            raise
    
    def query_equipment_metrics(self, equipment_id: int, metric_name: str, 
                              start: str = "-24h", stop: str = "now",
                              aggregation: Optional[str] = None) -> List[Dict]:
        """
        Récupère les métriques d'un équipement.
        
        Args:
            equipment_id: ID de l'équipement
            metric_name: Nom de la métrique
            start: Début de la période (ex: "-24h", "-7d", "2024-01-01T00:00:00Z")
            stop: Fin de la période (ex: "now", "2024-01-02T00:00:00Z")
            aggregation: Type d'agrégation (mean, max, min, sum, count)
        
        Returns:
            Liste des points de données
        """
        if not self.query_api:
            logger.warning("InfluxDB non configuré")
            return []
        
        try:
            if aggregation:
                query = f'''
                from(bucket: "{self.bucket}")
                    |> range(start: {start}, stop: {stop})
                    |> filter(fn: (r) => r["_measurement"] == "equipment_metrics")
                    |> filter(fn: (r) => r["equipment_id"] == "{equipment_id}")
                    |> filter(fn: (r) => r["metric_name"] == "{metric_name}")
                    |> filter(fn: (r) => r["_field"] == "value")
                    |> aggregateWindow(every: 1h, fn: {aggregation}, createEmpty: false)
                '''
            else:
                query = f'''
                from(bucket: "{self.bucket}")
                    |> range(start: {start}, stop: {stop})
                    |> filter(fn: (r) => r["_measurement"] == "equipment_metrics")
                    |> filter(fn: (r) => r["equipment_id"] == "{equipment_id}")
                    |> filter(fn: (r) => r["metric_name"] == "{metric_name}")
                    |> filter(fn: (r) => r["_field"] == "value")
                '''
            
            result = self.query_api.query(query=query)
            
            data = []
            for table in result:
                for record in table.records:
                    data.append({
                        'time': record.get_time(),
                        'value': record.get_value(),
                        'equipment_id': record.values.get('equipment_id'),
                        'metric_name': record.values.get('metric_name')
                    })
            
            return data
            
        except Exception as e:
            logger.error(f"Erreur lors de la requête: {e}")
            raise
    
    def calculate_equipment_availability(self, equipment_id: int, start: str = "-24h", 
                                       stop: str = "now") -> float:
        """
        Calcule le taux de disponibilité d'un équipement sur une période.
        
        Args:
            equipment_id: ID de l'équipement
            start: Début de la période
            stop: Fin de la période
        
        Returns:
            Taux de disponibilité en pourcentage (0-100)
        """
        if not self.query_api:
            return 0.0
        
        try:
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start}, stop: {stop})
                |> filter(fn: (r) => r["_measurement"] == "equipment_status_changes")
                |> filter(fn: (r) => r["equipment_id"] == "{equipment_id}")
                |> filter(fn: (r) => r["_field"] == "status_value")
                |> mean()
            '''
            
            result = self.query_api.query(query=query)
            
            if result and result[0].records:
                # La valeur moyenne donne le taux de disponibilité
                availability = result[0].records[0].get_value() * 100
                return round(availability, 2)
            
            return 100.0  # Si pas de données, on considère l'équipement comme disponible
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul de disponibilité: {e}")
            return 0.0
    
    def get_equipment_statistics(self, equipment_id: int, start: str = "-7d") -> Dict:
        """
        Récupère des statistiques complètes pour un équipement.
        
        Args:
            equipment_id: ID de l'équipement
            start: Début de la période d'analyse
        
        Returns:
            Dictionnaire avec les statistiques
        """
        stats = {
            'availability': self.calculate_equipment_availability(equipment_id, start),
            'status_changes': 0,
            'current_status': 'unknown',
            'metrics': {}
        }
        
        try:
            # Compter les changements de statut
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start})
                |> filter(fn: (r) => r["_measurement"] == "equipment_status_changes")
                |> filter(fn: (r) => r["equipment_id"] == "{equipment_id}")
                |> filter(fn: (r) => r["_field"] == "change_event")
                |> count()
            '''
            
            result = self.query_api.query(query=query)
            if result and result[0].records:
                stats['status_changes'] = result[0].records[0].get_value()
            
            # Récupérer le dernier statut
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start})
                |> filter(fn: (r) => r["_measurement"] == "equipment_status_changes")
                |> filter(fn: (r) => r["equipment_id"] == "{equipment_id}")
                |> last()
            '''
            
            result = self.query_api.query(query=query)
            for table in result:
                for record in table.records:
                    if 'new_status' in record.values:
                        stats['current_status'] = record.values['new_status']
            
            return stats
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {e}")
            return stats
    
    def test_connection(self) -> bool:
        """
        Teste la connexion à InfluxDB.
        
        Returns:
            True si la connexion est OK, False sinon
        """
        if not self.client:
            logger.warning("Client InfluxDB non initialisé")
            return False
        
        try:
            # Test simple avec une requête de santé
            health = self.client.health()
            if health.status == "pass":
                logger.info("Connexion InfluxDB OK")
                return True
            else:
                logger.warning(f"InfluxDB health check failed: {health.status}")
                return False
        except Exception as e:
            logger.error(f"Erreur de test de connexion InfluxDB: {e}")
            return False
    
    def get_bucket_info(self) -> Optional[Dict]:
        """
        Récupère les informations du bucket.
        
        Returns:
            Informations du bucket ou None
        """
        if not self.client:
            return None
        
        try:
            buckets_api = self.client.buckets_api()
            bucket = buckets_api.find_bucket_by_name(self.bucket)
            if bucket:
                return {
                    'id': bucket.id,
                    'name': bucket.name,
                    'org_id': bucket.org_id,
                    'retention_rules': bucket.retention_rules,
                    'created_at': bucket.created_at,
                    'updated_at': bucket.updated_at
                }
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos bucket: {e}")
            return None
    
    def delete_measurement(self, measurement: str, start: str = "-30d", stop: str = "now") -> bool:
        """
        Supprime toutes les données d'une mesure.
        
        Args:
            measurement: Nom de la mesure
            start: Début de la période à supprimer
            stop: Fin de la période à supprimer
        
        Returns:
            True si succès, False sinon
        """
        if not self.client:
            return False
        
        try:
            delete_api = self.client.delete_api()
            delete_api.delete(
                start=start,
                stop=stop,
                predicate=f'_measurement="{measurement}"',
                bucket=self.bucket,
                org=self.org
            )
            logger.info(f"Données supprimées pour la mesure {measurement}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression: {e}")
            return False
    
    def get_measurements(self) -> List[str]:
        """
        Récupère la liste des mesures disponibles.
        
        Returns:
            Liste des noms de mesures
        """
        if not self.query_api:
            return []
        
        try:
            query = f'''
            import "influxdata/influxdb/schema"
            schema.measurements(bucket: "{self.bucket}")
            '''
            
            result = self.query_api.query(query=query)
            measurements = []
            
            for table in result:
                for record in table.records:
                    measurements.append(record.get_value())
            
            return measurements
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des mesures: {e}")
            return []
    
    def get_field_keys(self, measurement: str) -> List[str]:
        """
        Récupère les clés de champs pour une mesure.
        
        Args:
            measurement: Nom de la mesure
        
        Returns:
            Liste des clés de champs
        """
        if not self.query_api:
            return []
        
        try:
            query = f'''
            import "influxdata/influxdb/schema"
            schema.fieldKeys(
                bucket: "{self.bucket}",
                predicate: (r) => r._measurement == "{measurement}"
            )
            '''
            
            result = self.query_api.query(query=query)
            fields = []
            
            for table in result:
                for record in table.records:
                    fields.append(record.get_value())
            
            return fields
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des champs: {e}")
            return []
    
    def get_tag_keys(self, measurement: str) -> List[str]:
        """
        Récupère les clés de tags pour une mesure.
        
        Args:
            measurement: Nom de la mesure
        
        Returns:
            Liste des clés de tags
        """
        if not self.query_api:
            return []
        
        try:
            query = f'''
            import "influxdata/influxdb/schema"
            schema.tagKeys(
                bucket: "{self.bucket}",
                predicate: (r) => r._measurement == "{measurement}"
            )
            '''
            
            result = self.query_api.query(query=query)
            tags = []
            
            for table in result:
                for record in table.records:
                    tags.append(record.get_value())
            
            return tags
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des tags: {e}")
            return []
    
    def write_points_batch(self, points: List[Point]) -> bool:
        """
        Écrit plusieurs points en lot.
        
        Args:
            points: Liste des points à écrire
        
        Returns:
            True si succès, False sinon
        """
        if not self.write_api or not points:
            return False
        
        try:
            self.write_api.write(bucket=self.bucket, record=points)
            logger.debug(f"Batch de {len(points)} points écrit avec succès")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture en lot: {e}")
            return False
    
    def query_raw(self, query: str) -> List[Dict]:
        """
        Exécute une requête Flux brute.
        
        Args:
            query: Requête Flux
        
        Returns:
            Résultats de la requête
        """
        if not self.query_api:
            return []
        
        try:
            result = self.query_api.query(query=query)
            data = []
            
            for table in result:
                for record in table.records:
                    data.append({
                        'time': record.get_time(),
                        'measurement': record.get_measurement(),
                        'field': record.get_field(),
                        'value': record.get_value(),
                        'tags': {k: v for k, v in record.values.items() 
                                if not k.startswith('_') and k not in ['result', 'table']}
                    })
            
            return data
        except Exception as e:
            logger.error(f"Erreur lors de la requête: {e}")
            return []
    
    def get_database_size(self) -> Optional[Dict]:
        """
        Récupère la taille de la base de données.
        
        Returns:
            Informations sur la taille ou None
        """
        try:
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -30d)
                |> group()
                |> count()
            '''
            
            result = self.query_api.query(query=query)
            
            if result and result[0].records:
                total_points = result[0].records[0].get_value()
                return {
                    'total_points': total_points,
                    'bucket': self.bucket,
                    'period': '30 days'
                }
            
            return None
        except Exception as e:
            logger.error(f"Erreur lors du calcul de la taille: {e}")
            return None
    
    def close(self):
        """Ferme la connexion à InfluxDB."""
        if self.client:
            self.client.close()
            logger.info("Connexion InfluxDB fermée")


# Instance singleton
influxdb_manager = InfluxDBManager()