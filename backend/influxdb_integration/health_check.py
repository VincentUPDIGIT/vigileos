"""
Health check pour InfluxDB - Intégration avec le système de santé de Django.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from influxdb_integration.client import influxdb_manager
from influxdb_integration.services import EquipmentAnalyticsService
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
@csrf_exempt
def influxdb_health_check(request):
    """
    Health check complet pour InfluxDB.
    
    Vérifie :
    - Connexion à InfluxDB
    - Existence du bucket
    - Capacité d'écriture/lecture
    - Performance des requêtes
    """
    health_status = {
        'service': 'influxdb',
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'checks': {},
        'metrics': {},
        'errors': []
    }
    
    try:
        # 1. Test de connexion
        connection_ok = influxdb_manager.test_connection()
        health_status['checks']['connection'] = {
            'status': 'pass' if connection_ok else 'fail',
            'message': 'InfluxDB connection test'
        }
        
        if not connection_ok:
            health_status['status'] = 'unhealthy'
            health_status['errors'].append('Cannot connect to InfluxDB')
            return JsonResponse(health_status, status=503)
        
        # 2. Test du bucket
        bucket_info = influxdb_manager.get_bucket_info()
        health_status['checks']['bucket'] = {
            'status': 'pass' if bucket_info else 'fail',
            'message': f'Bucket {influxdb_manager.bucket} accessibility'
        }
        
        if bucket_info:
            health_status['metrics']['bucket_id'] = bucket_info.get('id')
            health_status['metrics']['bucket_created'] = str(bucket_info.get('created_at'))
        else:
            health_status['status'] = 'degraded'
            health_status['errors'].append(f'Bucket {influxdb_manager.bucket} not found')
        
        # 3. Test de lecture
        try:
            measurements = influxdb_manager.get_measurements()
            health_status['checks']['read'] = {
                'status': 'pass',
                'message': 'Read operations working'
            }
            health_status['metrics']['measurements_count'] = len(measurements)
            health_status['metrics']['measurements'] = measurements
        except Exception as e:
            health_status['checks']['read'] = {
                'status': 'fail',
                'message': f'Read test failed: {str(e)}'
            }
            health_status['status'] = 'degraded'
            health_status['errors'].append(f'Read operations failing: {str(e)}')
        
        # 4. Test de performance des requêtes
        try:
            start_time = datetime.now()
            db_size = influxdb_manager.get_database_size()
            query_duration = (datetime.now() - start_time).total_seconds()
            
            health_status['checks']['performance'] = {
                'status': 'pass' if query_duration < 5.0 else 'warn',
                'message': f'Query performance test ({query_duration:.2f}s)'
            }
            health_status['metrics']['query_duration_seconds'] = query_duration
            
            if db_size:
                health_status['metrics']['total_points'] = db_size.get('total_points', 0)
            
            if query_duration > 10.0:
                health_status['status'] = 'degraded'
                health_status['errors'].append('Query performance degraded')
                
        except Exception as e:
            health_status['checks']['performance'] = {
                'status': 'fail',
                'message': f'Performance test failed: {str(e)}'
            }
            health_status['errors'].append(f'Performance test error: {str(e)}')
        
        # 5. Test de l'intégrité des données récentes
        try:
            # Vérifier qu'il y a des données récentes (dernières 24h)
            recent_query = f'''
            from(bucket: "{influxdb_manager.bucket}")
                |> range(start: -24h)
                |> limit(n: 1)
            '''
            
            recent_data = influxdb_manager.query_raw(recent_query)
            has_recent_data = len(recent_data) > 0
            
            health_status['checks']['data_freshness'] = {
                'status': 'pass' if has_recent_data else 'warn',
                'message': 'Recent data availability (24h)'
            }
            health_status['metrics']['has_recent_data'] = has_recent_data
            
            if not has_recent_data:
                health_status['errors'].append('No recent data found in last 24 hours')
                
        except Exception as e:
            health_status['checks']['data_freshness'] = {
                'status': 'fail',
                'message': f'Data freshness check failed: {str(e)}'
            }
            health_status['errors'].append(f'Data freshness error: {str(e)}')
        
        # 6. Configuration et limites
        health_status['metrics']['config'] = {
            'url': influxdb_manager.url,
            'org': influxdb_manager.org,
            'bucket': influxdb_manager.bucket,
            'client_configured': influxdb_manager.client is not None
        }
        
        # Déterminer le statut final
        failed_checks = [check for check in health_status['checks'].values() 
                        if check['status'] == 'fail']
        
        if failed_checks:
            health_status['status'] = 'unhealthy'
        elif health_status['errors']:
            health_status['status'] = 'degraded'
        
    except Exception as e:
        logger.error(f"InfluxDB health check failed: {e}")
        health_status['status'] = 'unhealthy'
        health_status['errors'].append(f'Health check exception: {str(e)}')
        health_status['checks']['exception'] = {
            'status': 'fail',
            'message': str(e)
        }
    
    # Déterminer le code de statut HTTP
    if health_status['status'] == 'healthy':
        status_code = 200
    elif health_status['status'] == 'degraded':
        status_code = 200  # Dégradé mais fonctionnel
    else:
        status_code = 503  # Service indisponible
    
    return JsonResponse(health_status, status=status_code)


@require_http_methods(["GET"])
@csrf_exempt
def influxdb_readiness_check(request):
    """
    Readiness check pour InfluxDB - vérifie si le service est prêt à recevoir du trafic.
    """
    readiness_status = {
        'service': 'influxdb',
        'ready': False,
        'timestamp': datetime.now().isoformat(),
        'checks': {}
    }
    
    try:
        # Test de connexion basique
        connection_ok = influxdb_manager.test_connection()
        readiness_status['checks']['connection'] = connection_ok
        
        # Test du bucket
        bucket_exists = influxdb_manager.get_bucket_info() is not None
        readiness_status['checks']['bucket'] = bucket_exists
        
        # Test de lecture simple
        try:
            influxdb_manager.get_measurements()
            readiness_status['checks']['read'] = True
        except:
            readiness_status['checks']['read'] = False
        
        # Service prêt si tous les tests passent
        readiness_status['ready'] = all(readiness_status['checks'].values())
        
    except Exception as e:
        logger.error(f"InfluxDB readiness check failed: {e}")
        readiness_status['ready'] = False
        readiness_status['error'] = str(e)
    
    status_code = 200 if readiness_status['ready'] else 503
    return JsonResponse(readiness_status, status=status_code)


@require_http_methods(["GET"])
@csrf_exempt
def influxdb_liveness_check(request):
    """
    Liveness check pour InfluxDB - vérifie si le service est vivant.
    """
    liveness_status = {
        'service': 'influxdb',
        'alive': False,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # Test de connexion minimal
        alive = influxdb_manager.test_connection()
        liveness_status['alive'] = alive
        
    except Exception as e:
        logger.error(f"InfluxDB liveness check failed: {e}")
        liveness_status['alive'] = False
        liveness_status['error'] = str(e)
    
    status_code = 200 if liveness_status['alive'] else 503
    return JsonResponse(liveness_status, status=status_code)


def get_influxdb_metrics_summary():
    """
    Récupère un résumé des métriques InfluxDB pour le monitoring.
    
    Returns:
        dict: Résumé des métriques
    """
    try:
        summary = {
            'timestamp': datetime.now().isoformat(),
            'connection_status': 'unknown',
            'measurements': [],
            'total_points': 0,
            'bucket_info': None,
            'recent_activity': False
        }
        
        # Test de connexion
        if influxdb_manager.test_connection():
            summary['connection_status'] = 'connected'
            
            # Informations du bucket
            bucket_info = influxdb_manager.get_bucket_info()
            if bucket_info:
                summary['bucket_info'] = {
                    'name': bucket_info.get('name'),
                    'id': bucket_info.get('id'),
                    'created_at': str(bucket_info.get('created_at'))
                }
            
            # Mesures disponibles
            measurements = influxdb_manager.get_measurements()
            summary['measurements'] = measurements
            
            # Taille de la base
            db_size = influxdb_manager.get_database_size()
            if db_size:
                summary['total_points'] = db_size.get('total_points', 0)
            
            # Activité récente
            try:
                recent_query = f'''
                from(bucket: "{influxdb_manager.bucket}")
                    |> range(start: -1h)
                    |> limit(n: 1)
                '''
                recent_data = influxdb_manager.query_raw(recent_query)
                summary['recent_activity'] = len(recent_data) > 0
            except:
                summary['recent_activity'] = False
                
        else:
            summary['connection_status'] = 'disconnected'
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting InfluxDB metrics summary: {e}")
        return {
            'timestamp': datetime.now().isoformat(),
            'connection_status': 'error',
            'error': str(e)
        }


def check_influxdb_alerts():
    """
    Vérifie les conditions d'alerte pour InfluxDB.
    
    Returns:
        list: Liste des alertes détectées
    """
    alerts = []
    
    try:
        # Vérifier la connexion
        if not influxdb_manager.test_connection():
            alerts.append({
                'level': 'critical',
                'message': 'InfluxDB connection failed',
                'timestamp': datetime.now().isoformat()
            })
            return alerts
        
        # Vérifier la taille de la base
        db_size = influxdb_manager.get_database_size()
        if db_size:
            total_points = db_size.get('total_points', 0)
            
            # Alerte si plus de 10M de points (ajustable)
            if total_points > 10_000_000:
                alerts.append({
                    'level': 'warning',
                    'message': f'Large database size: {total_points:,} points',
                    'timestamp': datetime.now().isoformat()
                })
        
        # Vérifier l'activité récente
        try:
            recent_query = f'''
            from(bucket: "{influxdb_manager.bucket}")
                |> range(start: -2h)
                |> limit(n: 1)
            '''
            recent_data = influxdb_manager.query_raw(recent_query)
            
            if not recent_data:
                alerts.append({
                    'level': 'warning',
                    'message': 'No recent data in InfluxDB (last 2 hours)',
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            alerts.append({
                'level': 'error',
                'message': f'Failed to check recent activity: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
        
        # Vérifier les performances des requêtes
        start_time = datetime.now()
        try:
            influxdb_manager.get_measurements()
            query_duration = (datetime.now() - start_time).total_seconds()
            
            if query_duration > 5.0:
                alerts.append({
                    'level': 'warning',
                    'message': f'Slow query performance: {query_duration:.2f}s',
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            alerts.append({
                'level': 'error',
                'message': f'Query performance test failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        alerts.append({
            'level': 'critical',
            'message': f'InfluxDB health check failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        })
    
    return alerts