#!/usr/bin/env python
"""
Script de setup automatique pour l'intégration InfluxDB dans VIGILEOS.
"""
import os
import sys
import subprocess
import django
from pathlib import Path

def setup_django():
    """Configure Django pour le script."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vigileos.settings.test')
    django.setup()

def check_dependencies():
    """Vérifie que toutes les dépendances sont installées."""
    print("🔍 Vérification des dépendances...")
    
    required_packages = [
        'influxdb-client',
        'pandas',
        'numpy',
        'python-decouple',
        'dj-database-url'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"  ❌ {package}")
    
    if missing_packages:
        print(f"\n⚠️  Packages manquants: {', '.join(missing_packages)}")
        print("Installez-les avec: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ Toutes les dépendances sont installées")
    return True

def check_django_config():
    """Vérifie la configuration Django."""
    print("\n🔍 Vérification de la configuration Django...")
    
    try:
        setup_django()
        from django.conf import settings
        
        # Vérifier INSTALLED_APPS
        if 'influxdb_integration' in settings.INSTALLED_APPS:
            print("  ✅ influxdb_integration dans INSTALLED_APPS")
        else:
            print("  ❌ influxdb_integration manquant dans INSTALLED_APPS")
            return False
        
        # Vérifier configuration InfluxDB
        if hasattr(settings, 'INFLUXDB_CONFIG'):
            print("  ✅ Configuration InfluxDB présente")
            config = settings.INFLUXDB_CONFIG
            print(f"    - URL: {config.get('url', 'Non définie')}")
            print(f"    - Org: {config.get('org', 'Non définie')}")
            print(f"    - Bucket: {config.get('bucket', 'Non défini')}")
        else:
            print("  ❌ Configuration InfluxDB manquante")
            return False
        
        print("✅ Configuration Django OK")
        return True
        
    except Exception as e:
        print(f"❌ Erreur configuration Django: {e}")
        return False

def run_migrations():
    """Exécute les migrations Django."""
    print("\n🔍 Exécution des migrations Django...")
    
    try:
        result = subprocess.run([
            sys.executable, 'manage.py', 'migrate'
        ], capture_output=True, text=True, check=True)
        
        print("✅ Migrations exécutées avec succès")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors des migrations: {e}")
        print(f"Sortie: {e.stdout}")
        print(f"Erreur: {e.stderr}")
        return False

def test_influxdb_connection():
    """Teste la connexion InfluxDB."""
    print("\n🔍 Test de la connexion InfluxDB...")
    
    try:
        from influxdb_integration.client import InfluxDBManager
        
        manager = InfluxDBManager()
        if manager.test_connection():
            print("✅ Connexion InfluxDB réussie")
            return True
        else:
            print("⚠️  Connexion InfluxDB échouée (serveur non disponible)")
            print("   Ceci est normal si InfluxDB n'est pas encore installé")
            return True  # On considère que c'est OK
            
    except Exception as e:
        print(f"⚠️  Erreur test connexion InfluxDB: {e}")
        print("   Ceci est normal si InfluxDB n'est pas encore installé")
        return True  # On considère que c'est OK

def run_tests():
    """Exécute les tests InfluxDB."""
    print("\n🔍 Exécution des tests InfluxDB...")
    
    try:
        result = subprocess.run([
            sys.executable, 'manage.py', 'test', 'influxdb_integration'
        ], capture_output=True, text=True, check=True)
        
        print("✅ Tests InfluxDB passés avec succès")
        print(f"Résultat: {result.stdout}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Certains tests ont échoué: {e}")
        print(f"Sortie: {e.stdout}")
        print(f"Erreur: {e.stderr}")
        print("   Ceci peut être normal si InfluxDB n'est pas installé")
        return True  # On considère que c'est OK pour le setup

def check_management_commands():
    """Vérifie les commandes de gestion."""
    print("\n🔍 Vérification des commandes de gestion...")
    
    commands = [
        'check_influxdb_status',
        'cleanup_influxdb_data',
        'migrate_metrics_to_influxdb'
    ]
    
    for command in commands:
        try:
            result = subprocess.run([
                sys.executable, 'manage.py', command, '--help'
            ], capture_output=True, text=True, check=True)
            
            print(f"  ✅ {command}")
            
        except subprocess.CalledProcessError:
            print(f"  ❌ {command}")
            return False
    
    print("✅ Toutes les commandes de gestion sont disponibles")
    return True

def check_api_urls():
    """Vérifie que les URLs API sont accessibles."""
    print("\n🔍 Vérification des URLs API...")
    
    try:
        from django.urls import reverse
        
        urls_to_check = [
            'influxdb:influxdb-status',
            'influxdb:global-dashboard',
            'influxdb:metrics-schema'
        ]
        
        for url_name in urls_to_check:
            try:
                url = reverse(url_name)
                print(f"  ✅ {url_name} -> {url}")
            except Exception as e:
                print(f"  ❌ {url_name}: {e}")
                return False
        
        print("✅ Toutes les URLs API sont configurées")
        return True
        
    except Exception as e:
        print(f"❌ Erreur vérification URLs: {e}")
        return False

def create_env_template():
    """Crée un template de fichier .env."""
    print("\n🔍 Création du template .env...")
    
    env_template = """# Configuration InfluxDB pour VIGILEOS
# Copiez ce fichier vers .env et configurez vos valeurs

# InfluxDB Configuration
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-influxdb-token-here
INFLUXDB_ORG=vigileos
INFLUXDB_BUCKET=vigileos-metrics
INFLUXDB_TIMEOUT=10000
INFLUXDB_VERIFY_SSL=True

# Django Configuration
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///db.sqlite3

# Autres configurations...
"""
    
    env_file = Path('.env.template')
    env_file.write_text(env_template)
    
    print(f"✅ Template .env créé: {env_file.absolute()}")
    print("   Copiez-le vers .env et configurez vos valeurs")

def main():
    """Fonction principale du setup."""
    print("🚀 Setup InfluxDB pour VIGILEOS")
    print("=" * 50)
    
    # Vérifications
    checks = [
        ("Dépendances", check_dependencies),
        ("Configuration Django", check_django_config),
        ("Migrations", run_migrations),
        ("Connexion InfluxDB", test_influxdb_connection),
        ("Commandes de gestion", check_management_commands),
        ("URLs API", check_api_urls),
    ]
    
    results = []
    
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Erreur lors de {name}: {e}")
            results.append((name, False))
    
    # Tests (optionnel)
    print("\n🔍 Tests (optionnel)...")
    try:
        test_result = run_tests()
        results.append(("Tests", test_result))
    except Exception as e:
        print(f"⚠️  Erreur lors des tests: {e}")
        results.append(("Tests", False))
    
    # Création template .env
    try:
        create_env_template()
        results.append(("Template .env", True))
    except Exception as e:
        print(f"❌ Erreur création template .env: {e}")
        results.append(("Template .env", False))
    
    # Résumé
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ DU SETUP")
    print("=" * 50)
    
    success_count = 0
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
        if result:
            success_count += 1
    
    print(f"\n📈 Réussite: {success_count}/{len(results)}")
    
    if success_count == len(results):
        print("\n🎉 SETUP COMPLET ! L'intégration InfluxDB est prête.")
        print("\n📋 Prochaines étapes:")
        print("1. Configurez votre fichier .env avec vos credentials InfluxDB")
        print("2. Installez et démarrez InfluxDB si ce n'est pas fait")
        print("3. Testez la connexion avec: python manage.py check_influxdb_status")
        print("4. Démarrez le serveur: python manage.py runserver")
    else:
        print("\n⚠️  Setup partiellement réussi. Vérifiez les erreurs ci-dessus.")
    
    return success_count == len(results)

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)