# InfluxDB Integration pour VIGILEOS

## Vue d'ensemble

Ce module fournit une intégration complète d'InfluxDB dans l'application VIGILEOS pour la surveillance d'équipements réseau. Il permet de stocker, analyser et visualiser les métriques de performance et de disponibilité des équipements en temps réel.

## Structure

```
influxdb_integration/
├── __init__.py          # Initialisation du module
├── apps.py              # Configuration Django et signaux
├── client.py            # Client InfluxDB (connexion, écriture, lecture)
├── services.py          # Services métier (métriques, analyses)
├── views.py             # API REST endpoints
├── urls.py              # Routes URL
├── tests.py             # Tests unitaires
└── management/
    └── commands/
        └── simulate_equipment_metrics.py  # Commande de simulation
```

## Fonctionnalités principales

### 1. Client InfluxDB (`client.py`)

- **InfluxDBManager** : Gère la connexion et les opérations de base
  - `test_connection()` : Vérifie la connexion
  - `write_data()` : Écrit des données
  - `query_data()` : Lit des données
  - `delete_data()` : Supprime des données

### 2. Services (`services.py`)

- **EquipmentMetricsService** : Enregistrement des métriques
  - `record_metric()` : Métrique générique
  - `record_availability()` : Disponibilité
  - `record_performance()` : Performances (CPU, mémoire, temps de réponse)
  - `record_status_change()` : Changements de statut

- **EquipmentAnalyticsService** : Analyse des données
  - `get_equipment_metrics()` : Récupère les métriques
  - `calculate_availability()` : Calcule le taux de disponibilité
  - `get_performance_stats()` : Statistiques de performance
  - `get_status_history()` : Historique des statuts

### 3. API REST (`views.py`)

- `/api/equipment/{id}/metrics/` : Métriques d'un équipement
- `/api/influxdb/dashboard/` : Tableau de bord global
- `/api/influxdb/availability-report/` : Rapport de disponibilité

### 4. Signaux Django (`apps.py`)

- Enregistrement automatique lors des changements de statut
- Métriques de disponibilité en temps réel

## Installation

1. Les dépendances sont déjà dans `requirements/base.txt`
2. Les settings Django sont configurés
3. Docker Compose inclut le service InfluxDB

## Utilisation

### Enregistrer des métriques

```python
from influxdb_integration.services import EquipmentMetricsService

service = EquipmentMetricsService()
service.record_metric(
    equipment_id=1,
    metric_type='temperature',
    value=25.5,
    tags={'sensor': 'temp_01'}
)
```

### Analyser les données

```python
from influxdb_integration.services import EquipmentAnalyticsService
from datetime import datetime, timedelta

analytics = EquipmentAnalyticsService()
availability = analytics.calculate_availability(
    equipment_id=1,
    start_time=datetime.now() - timedelta(days=7)
)
```

### API REST

```bash
# Obtenir les métriques
curl http://localhost:8000/api/equipment/1/metrics/

# Tableau de bord
curl http://localhost:8000/api/influxdb/dashboard/
```

## Tests

```bash
# Exécuter les tests
docker-compose exec web python manage.py test influxdb_integration

# Avec coverage
docker-compose exec web coverage run --source='influxdb_integration' manage.py test influxdb_integration
docker-compose exec web coverage report
```

## Configuration

Variables d'environnement requises :

- `INFLUXDB_URL` : URL du serveur InfluxDB
- `INFLUXDB_TOKEN` : Token d'authentification
- `INFLUXDB_ORG` : Organisation InfluxDB
- `INFLUXDB_BUCKET` : Bucket pour les données

## Maintenance

### Commandes de gestion

```bash
# Simuler des métriques
python manage.py simulate_equipment_metrics --equipment-id=1 --duration=3600

# Nettoyer les anciennes données
python manage.py cleanup_influxdb_data --older-than=90

# Vérifier le statut
python manage.py check_influxdb_status
```

### Monitoring

- Vérifier les logs : `docker-compose logs influxdb`
- Interface web : http://localhost:8086
- Métriques système : disponibles dans le dashboard

## Dépannage

### Problèmes courants

1. **Erreur de connexion** : Vérifier que InfluxDB est démarré et accessible
2. **Pas de données** : Vérifier les signaux Django et les permissions
3. **Performances** : Ajuster la rétention et les agrégations

### Debug

```python
# Activer le mode debug
import logging
logging.getLogger('influxdb_integration').setLevel(logging.DEBUG)
```

## Contribution

1. Créer une branche feature
2. Ajouter des tests
3. Documenter les changements
4. Soumettre une PR

## Licence

Voir le fichier LICENSE du projet principal.