"""
Tests pour l'intégration InfluxDB avec mocking complet.
"""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
from equipment.models import Equipment
from sites.models import Site
from users.models import Company
from influxdb_integration.client import InfluxDBManager
from influxdb_integration.services import EquipmentMetricsService, EquipmentAnalyticsService

# Configuration de test pour éviter les connexions InfluxDB réelles
TEST_INFLUXDB_CONFIG = {
    'url': 'http://test-influxdb:8086',
    'token': 'test-token',
    'org': 'test-org',
    'bucket': 'test-bucket',
    'timeout': 5000,
    'verify_ssl': False,
}

User = get_user_model()


@override_settings(INFLUXDB_CONFIG=TEST_INFLUXDB_CONFIG)
class InfluxDBManagerTestCase(TestCase):
    """Tests pour le gestionnaire InfluxDB."""
    
    def setUp(self):
        with patch('influxdb_integration.client.InfluxDBClient'):
            self.manager = InfluxDBManager()
    
    @patch('influxdb_integration.client.InfluxDBClient')
    def test_connection_success(self, mock_client):
        """Test de connexion réussie."""
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.return_value.health.return_value = mock_health
        
        self.manager.client = mock_client.return_value
        result = self.manager.test_connection()
        
        self.assertTrue(result)
    
    @patch('influxdb_integration.client.InfluxDBClient')
    def test_connection_failure(self, mock_client):
        """Test de connexion échouée."""
        mock_client.return_value.health.side_effect = Exception("Connection failed")
        
        self.manager.client = mock_client.return_value
        result = self.manager.test_connection()
        
        self.assertFalse(result)
    
    @patch('influxdb_integration.client.influxdb_manager')
    def test_write_equipment_metric(self, mock_manager):
        """Test d'écriture de métrique."""
        mock_manager.write_api = MagicMock()
        
        self.manager.write_equipment_metric(
            equipment_id=1,
            metric_name='cpu_usage',
            value=75.5,
            tags={'location': 'server_room'}
        )
        
        mock_manager.write_api.write.assert_called_once()
    
    def test_query_equipment_metrics_no_client(self):
        """Test de requête sans client."""
        self.manager.query_api = None
        result = self.manager.query_equipment_metrics(1, 'cpu_usage')
        self.assertEqual(result, [])


@override_settings(INFLUXDB_CONFIG=TEST_INFLUXDB_CONFIG)
class EquipmentMetricsServiceTestCase(TestCase):
    """Tests pour le service de métriques."""
    
    def setUp(self):
        # Créer des données de test
        self.company = Company.objects.create(
            name="Test Company",
            address="123 Test St"
        )
        
        self.site = Site.objects.create(
            name="Test Site",
            address="456 Site Ave",
            company=self.company
        )
        
        self.equipment = Equipment.objects.create(
            name="Test Server",
            type="server",
            site=self.site,
            ip_address="192.168.1.100"
        )
    
    @patch('influxdb_integration.services.influxdb_manager')
    def test_record_metric(self, mock_manager):
        """Test d'enregistrement de métrique."""
        EquipmentMetricsService.record_metric(
            equipment_id=self.equipment.id,
            metric_type='cpu_usage',
            value=75.5,
            tags={'test': 'value'}
        )
        
        mock_manager.write_equipment_metric.assert_called_once()
    
    @patch('influxdb_integration.services.influxdb_manager')
    def test_record_availability(self, mock_manager):
        """Test d'enregistrement de disponibilité."""
        EquipmentMetricsService.record_availability(
            equipment_id=self.equipment.id,
            is_available=True,
            response_time=45.2
        )
        
        mock_manager.write_equipment_metric.assert_called_once()
    
    @patch('influxdb_integration.services.influxdb_manager')
    def test_record_performance(self, mock_manager):
        """Test d'enregistrement de performance."""
        EquipmentMetricsService.record_performance(
            equipment_id=self.equipment.id,
            cpu_usage=75.5,
            memory_usage=60.2,
            response_time=120.0
        )
        
        # Doit être appelé 3 fois (une fois par métrique)
        self.assertEqual(mock_manager.write_equipment_metric.call_count, 3)
    
    @patch('influxdb_integration.services.influxdb_manager')
    def test_bulk_record_metrics(self, mock_manager):
        """Test d'enregistrement en lot."""
        metrics_data = [
            {
                'equipment_id': self.equipment.id,
                'metric_type': 'cpu_usage',
                'value': 75.5
            },
            {
                'equipment_id': self.equipment.id,
                'metric_type': 'memory_usage',
                'value': 60.2
            }
        ]
        
        mock_manager.write_points_batch.return_value = True
        
        result = EquipmentMetricsService.bulk_record_metrics(metrics_data)
        
        self.assertEqual(result['success'], 2)
        self.assertEqual(result['errors'], 0)
        mock_manager.write_points_batch.assert_called_once()


@override_settings(INFLUXDB_CONFIG=TEST_INFLUXDB_CONFIG)
class EquipmentAnalyticsServiceTestCase(TestCase):
    """Tests pour le service d'analytics."""
    
    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            address="123 Test St"
        )
        
        self.site = Site.objects.create(
            name="Test Site",
            address="456 Site Ave",
            company=self.company
        )
        
        self.equipment = Equipment.objects.create(
            name="Test Server",
            type="server",
            site=self.site
        )
    
    @patch('influxdb_integration.services.influxdb_manager')
    def test_calculate_availability(self, mock_manager):
        """Test de calcul de disponibilité."""
        mock_manager.calculate_equipment_availability.return_value = 95.5
        
        start_time = datetime.now() - timedelta(hours=24)
        end_time = datetime.now()
        
        availability = EquipmentAnalyticsService.calculate_availability(
            equipment_id=self.equipment.id,
            start_time=start_time,
            end_time=end_time
        )
        
        self.assertEqual(availability, 95.5)
        mock_manager.calculate_equipment_availability.assert_called_once()
    
    @patch('influxdb_integration.services.influxdb_manager')
    def test_get_performance_stats(self, mock_manager):
        """Test de récupération des statistiques de performance."""
        mock_data = [{'value': 75.5}, {'value': 80.0}, {'value': 70.0}]
        mock_manager.query_equipment_metrics.return_value = mock_data
        
        start_time = datetime.now() - timedelta(hours=24)
        end_time = datetime.now()
        
        stats = EquipmentAnalyticsService.get_performance_stats(
            equipment_id=self.equipment.id,
            start_time=start_time,
            end_time=end_time
        )
        
        self.assertIn('cpu_usage_avg', stats)
        self.assertIn('memory_usage_avg', stats)
        self.assertIn('response_time_avg', stats)
    
    @patch('influxdb_integration.services.cache')
    @patch('influxdb_integration.services.EquipmentAnalyticsService.calculate_availability')
    def test_get_global_dashboard_data_cached(self, mock_availability, mock_cache):
        """Test du dashboard global avec cache."""
        cached_data = {'summary': {'total_equipment': 1}}
        mock_cache.get.return_value = cached_data
        
        result = EquipmentAnalyticsService.get_global_dashboard_data(hours=24)
        
        self.assertEqual(result, cached_data)
        mock_cache.get.assert_called_once()
    
    def test_get_alerts_from_metrics(self):
        """Test de génération d'alertes."""
        with patch.object(EquipmentAnalyticsService, 'get_performance_stats') as mock_stats:
            mock_stats.return_value = {
                'cpu_usage_avg': 90.0,  # Au-dessus du seuil warning (80)
                'memory_usage_avg': 50.0,
                'response_time_avg': 100.0
            }
            
            alerts = EquipmentAnalyticsService.get_alerts_from_metrics(
                equipment_id=self.equipment.id,
                hours=24
            )
            
            # Doit générer une alerte pour CPU
            cpu_alerts = [a for a in alerts if a['metric_type'] == 'cpu_usage']
            self.assertEqual(len(cpu_alerts), 1)
            self.assertEqual(cpu_alerts[0]['severity'], 'warning')


@override_settings(INFLUXDB_CONFIG=TEST_INFLUXDB_CONFIG)
class InfluxDBAPITestCase(APITestCase):
    """Tests pour l'API InfluxDB."""
    
    def setUp(self):
        # Créer un utilisateur de test
        self.company = Company.objects.create(
            name="Test Company",
            address="123 Test St"
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            company=self.company
        )
        
        self.site = Site.objects.create(
            name="Test Site",
            address="456 Site Ave",
            company=self.company
        )
        
        self.equipment = Equipment.objects.create(
            name="Test Server",
            type="server",
            site=self.site
        )
        
        # Authentifier l'utilisateur
        self.client.force_authenticate(user=self.user)
    
    @patch('influxdb_integration.views.EquipmentMetricsService.record_metric')
    def test_record_equipment_metric(self, mock_record):
        """Test d'enregistrement de métrique via API."""
        url = reverse('influxdb:record-metric', kwargs={'equipment_id': self.equipment.id})
        data = {
            'metric_name': 'cpu_usage',
            'value': 75.5,
            'additional_fields': {'process_count': 125}
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_record.assert_called_once()
    
    def test_record_equipment_metric_invalid_data(self):
        """Test d'enregistrement avec données invalides."""
        url = reverse('influxdb:record-metric', kwargs={'equipment_id': self.equipment.id})
        data = {
            'metric_name': 'cpu_usage'
            # Manque 'value'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('influxdb_integration.views.EquipmentMetricsService.record_availability')
    def test_record_availability_check(self, mock_record):
        """Test d'enregistrement de disponibilité via API."""
        url = reverse('influxdb:record-availability', kwargs={'equipment_id': self.equipment.id})
        data = {
            'is_available': True,
            'response_time': 45.2
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_record.assert_called_once()
    
    @patch('influxdb_integration.views.influxdb_manager')
    def test_get_equipment_metrics(self, mock_manager):
        """Test de récupération de métriques via API."""
        mock_manager.query_equipment_metrics.return_value = [
            {'time': '2024-01-01T12:00:00Z', 'value': 75.5}
        ]
        
        url = reverse('influxdb:get-metrics', kwargs={'equipment_id': self.equipment.id})
        response = self.client.get(url, {'metric_name': 'cpu_usage', 'period': '24h'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
    
    @patch('influxdb_integration.views.EquipmentAnalyticsService.get_global_dashboard_data')
    def test_get_global_dashboard(self, mock_dashboard):
        """Test du dashboard global via API."""
        mock_dashboard.return_value = {
            'summary': {'total_equipment': 1},
            'equipment_details': []
        }
        
        url = reverse('influxdb:global-dashboard')
        response = self.client.get(url, {'hours': 24})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
    
    @patch('influxdb_integration.views.influxdb_manager')
    def test_get_influxdb_status(self, mock_manager):
        """Test du statut InfluxDB via API."""
        mock_manager.test_connection.return_value = True
        mock_manager.get_bucket_info.return_value = {'name': 'test_bucket'}
        mock_manager.get_measurements.return_value = ['equipment_metrics']
        mock_manager.get_database_size.return_value = {'total_points': 1000}
        
        url = reverse('influxdb:influxdb-status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'connected')
    
    @patch('influxdb_integration.views.EquipmentMetricsService.bulk_record_metrics')
    def test_bulk_record_metrics(self, mock_bulk):
        """Test d'enregistrement en lot via API."""
        mock_bulk.return_value = {'success': 2, 'errors': 0, 'total': 2}
        
        url = reverse('influxdb:bulk-metrics')
        data = {
            'metrics': [
                {
                    'equipment_id': self.equipment.id,
                    'metric_type': 'cpu_usage',
                    'value': 75.5
                },
                {
                    'equipment_id': self.equipment.id,
                    'metric_type': 'memory_usage',
                    'value': 60.2
                }
            ]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)
    
    def test_bulk_record_metrics_empty(self):
        """Test d'enregistrement en lot avec données vides."""
        url = reverse('influxdb:bulk-metrics')
        data = {'metrics': []}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_unauthorized_access(self):
        """Test d'accès non autorisé."""
        self.client.force_authenticate(user=None)
        
        url = reverse('influxdb:global-dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(INFLUXDB_CONFIG=TEST_INFLUXDB_CONFIG)
class InfluxDBSignalsTestCase(TestCase):
    """Tests pour les signaux Django."""
    
    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            address="123 Test St"
        )
        
        self.site = Site.objects.create(
            name="Test Site",
            address="456 Site Ave",
            company=self.company
        )
    
    @patch('influxdb_integration.services.influxdb_manager')
    def test_equipment_status_change_signal(self, mock_manager):
        """Test du signal de changement de statut."""
        # Créer un équipement
        equipment = Equipment.objects.create(
            name="Test Server",
            type="server",
            site=self.site,
            status='online'
        )
        
        # Changer le statut
        equipment.status = 'offline'
        equipment.save()
        
        # Vérifier que le signal a été déclenché
        mock_manager.write_equipment_status_change.assert_called()
    
    @patch('influxdb_integration.services.influxdb_manager')
    def test_new_equipment_signal(self, mock_manager):
        """Test du signal de création d'équipement."""
        Equipment.objects.create(
            name="New Server",
            type="server",
            site=self.site,
            status='online'
        )
        
        # Vérifier que le signal a été déclenché pour le nouvel équipement
        mock_manager.write_equipment_status_change.assert_called()