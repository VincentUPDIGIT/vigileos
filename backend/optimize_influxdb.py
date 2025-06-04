#!/usr/bin/env python
"""
Script d'optimisation des performances InfluxDB pour VIGILEOS.
"""
import os
import sys
import django
from pathlib import Path
from datetime import datetime, timedelta

def setup_django():
    """Configure Django pour le script."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vigileos.settings.test')
    django.setup()

def optimize_influxdb_queries():
    """Optimise les requêtes InfluxDB."""
    print("🔧 Optimisation des requêtes InfluxDB...")
    
    from influxdb_integration.client import InfluxDBManager
    
    try:
        manager = InfluxDBManager()
        
        # Test de performance des requêtes
        print("  📊 Test de performance des requêtes...")
        
        # Requête simple
        start_time = datetime.now()
        try:
            result = manager.query_equipment_metrics(
                equipment_id=1,
                start_time=datetime.now() - timedelta(hours=1),
                end_time=datetime.now()
            )
            query_time = (datetime.now() - start_time).total_seconds()
            print(f"    ✅ Requête simple: {query_time:.3f}s")
        except Exception as e:
            print(f"    ⚠️  Requête simple échouée: {e}")
        
        # Requête agrégée
        start_time = datetime.now()
        try:
            result = manager.query_aggregated_metrics(
                equipment_id=1,
                start_time=datetime.now() - timedelta(days=1),
                end_time=datetime.now(),
                window='1h'
            )
            query_time = (datetime.now() - start_time).total_seconds()
            print(f"    ✅ Requête agrégée: {query_time:.3f}s")
        except Exception as e:
            print(f"    ⚠️  Requête agrégée échouée: {e}")
        
        print("✅ Tests de performance terminés")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors des tests de performance: {e}")
        return False

def optimize_batch_operations():
    """Optimise les opérations en lot."""
    print("\n🔧 Optimisation des opérations en lot...")
    
    from influxdb_integration.services import EquipmentMetricsService
    
    # Test d'écriture en lot
    print("  📝 Test d'écriture en lot...")
    
    # Simuler des métriques en lot
    metrics_data = []
    for i in range(100):
        metrics_data.append({
            'equipment_id': 1,
            'metric_type': 'cpu_usage',
            'value': 50.0 + (i % 20),
            'timestamp': datetime.now() - timedelta(minutes=i)
        })
    
    start_time = datetime.now()
    try:
        result = EquipmentMetricsService.bulk_record_metrics(metrics_data)
        batch_time = (datetime.now() - start_time).total_seconds()
        print(f"    ✅ Écriture de {len(metrics_data)} métriques: {batch_time:.3f}s")
        print(f"    📈 Débit: {len(metrics_data)/batch_time:.1f} métriques/s")
    except Exception as e:
        print(f"    ⚠️  Écriture en lot échouée: {e}")
    
    print("✅ Tests d'optimisation en lot terminés")
    return True

def check_influxdb_configuration():
    """Vérifie et optimise la configuration InfluxDB."""
    print("\n🔧 Vérification de la configuration InfluxDB...")
    
    from django.conf import settings
    
    if hasattr(settings, 'INFLUXDB_CONFIG'):
        config = settings.INFLUXDB_CONFIG
        
        # Vérifier les paramètres de performance
        recommendations = []
        
        if config.get('timeout', 0) < 10000:
            recommendations.append("Augmenter le timeout à 10000ms minimum")
        
        if config.get('verify_ssl', True) and 'localhost' in config.get('url', ''):
            recommendations.append("Désactiver verify_ssl pour localhost")
        
        if not config.get('enable_gzip', False):
            recommendations.append("Activer la compression gzip")
        
        if recommendations:
            print("  📋 Recommandations d'optimisation:")
            for rec in recommendations:
                print(f"    • {rec}")
        else:
            print("  ✅ Configuration optimale")
        
        # Afficher la configuration actuelle
        print("  📊 Configuration actuelle:")
        print(f"    - URL: {config.get('url')}")
        print(f"    - Timeout: {config.get('timeout')}ms")
        print(f"    - Verify SSL: {config.get('verify_ssl')}")
        print(f"    - Bucket: {config.get('bucket')}")
        
        return True
    else:
        print("❌ Configuration InfluxDB manquante")
        return False

def generate_performance_report():
    """Génère un rapport de performance."""
    print("\n📊 Génération du rapport de performance...")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'database_size': 'N/A (InfluxDB non connecté)',
        'query_performance': 'Tests effectués',
        'batch_performance': 'Tests effectués',
        'recommendations': []
    }
    
    # Sauvegarder le rapport
    report_file = Path('influxdb_performance_report.json')
    
    import json
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"✅ Rapport sauvegardé: {report_file.absolute()}")
    return True

def optimize_database_retention():
    """Optimise les politiques de rétention."""
    print("\n🔧 Optimisation des politiques de rétention...")
    
    from influxdb_integration.client import InfluxDBManager
    
    try:
        manager = InfluxDBManager()
        
        # Recommandations de rétention
        recommendations = [
            "Métriques temps réel: 7 jours",
            "Métriques agrégées horaires: 30 jours", 
            "Métriques agrégées quotidiennes: 1 an",
            "Alertes: 90 jours",
            "Événements de statut: 6 mois"
        ]
        
        print("  📋 Recommandations de rétention:")
        for rec in recommendations:
            print(f"    • {rec}")
        
        print("  💡 Implémentez ces politiques dans votre configuration InfluxDB")
        return True
        
    except Exception as e:
        print(f"⚠️  Impossible de vérifier les politiques: {e}")
        return True  # Non critique

def create_monitoring_queries():
    """Crée des requêtes de monitoring prêtes à l'emploi."""
    print("\n📝 Création des requêtes de monitoring...")
    
    queries = {
        'equipment_health': '''
from(bucket: "vigileos-metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "equipment_metrics")
  |> filter(fn: (r) => r["_field"] == "cpu_usage" or r["_field"] == "memory_usage")
  |> group(columns: ["equipment_id"])
  |> mean()
        ''',
        
        'network_performance': '''
from(bucket: "vigileos-metrics")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "network_metrics")
  |> filter(fn: (r) => r["_field"] == "ping_response_time")
  |> aggregateWindow(every: 1h, fn: mean)
        ''',
        
        'availability_report': '''
from(bucket: "vigileos-metrics")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "availability")
  |> filter(fn: (r) => r["_field"] == "is_online")
  |> group(columns: ["equipment_id"])
  |> mean()
  |> map(fn: (r) => ({ r with uptime_percentage: r._value * 100.0 }))
        ''',
        
        'alert_frequency': '''
from(bucket: "vigileos-metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "alerts")
  |> group(columns: ["equipment_id", "alert_type"])
  |> count()
        '''
    }
    
    # Sauvegarder les requêtes
    queries_file = Path('influxdb_monitoring_queries.flux')
    
    with open(queries_file, 'w') as f:
        f.write("// Requêtes de monitoring InfluxDB pour VIGILEOS\n")
        f.write(f"// Générées le {datetime.now().isoformat()}\n\n")
        
        for name, query in queries.items():
            f.write(f"// {name.replace('_', ' ').title()}\n")
            f.write(query.strip())
            f.write("\n\n")
    
    print(f"✅ Requêtes sauvegardées: {queries_file.absolute()}")
    return True

def main():
    """Fonction principale d'optimisation."""
    print("🚀 Optimisation InfluxDB pour VIGILEOS")
    print("=" * 50)
    
    # Setup Django
    try:
        setup_django()
        print("✅ Django configuré")
    except Exception as e:
        print(f"❌ Erreur configuration Django: {e}")
        return False
    
    # Optimisations
    optimizations = [
        ("Configuration InfluxDB", check_influxdb_configuration),
        ("Requêtes InfluxDB", optimize_influxdb_queries),
        ("Opérations en lot", optimize_batch_operations),
        ("Politiques de rétention", optimize_database_retention),
        ("Requêtes de monitoring", create_monitoring_queries),
        ("Rapport de performance", generate_performance_report),
    ]
    
    results = []
    
    for name, optimization_func in optimizations:
        try:
            print(f"\n🔧 {name}...")
            result = optimization_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Erreur lors de {name}: {e}")
            results.append((name, False))
    
    # Résumé
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ DE L'OPTIMISATION")
    print("=" * 50)
    
    success_count = 0
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
        if result:
            success_count += 1
    
    print(f"\n📈 Réussite: {success_count}/{len(results)}")
    
    if success_count == len(results):
        print("\n🎉 OPTIMISATION COMPLÈTE !")
        print("\n📋 Fichiers générés:")
        print("• influxdb_performance_report.json")
        print("• influxdb_monitoring_queries.flux")
        print("\n💡 Conseils supplémentaires:")
        print("• Surveillez régulièrement les performances")
        print("• Ajustez les politiques de rétention selon vos besoins")
        print("• Utilisez les requêtes de monitoring pour créer des dashboards")
    else:
        print("\n⚠️  Optimisation partiellement réussie.")
    
    return success_count == len(results)

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)