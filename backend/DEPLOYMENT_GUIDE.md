# Guide de Déploiement InfluxDB pour VIGILEOS

## 📋 Vue d'Ensemble

Ce guide vous accompagne dans le déploiement complet de l'intégration InfluxDB pour VIGILEOS, depuis l'installation jusqu'à la mise en production.

## 🚀 Déploiement Rapide

### 1. Prérequis

```bash
# Vérifier Python
python --version  # >= 3.8

# Vérifier pip
pip --version

# Vérifier Django
python -c "import django; print(django.get_version())"  # >= 4.2
```

### 2. Installation Automatique

```bash
# Cloner le projet
git clone <votre-repo>
cd vigileos/backend

# Exécuter le setup automatique
python setup_influxdb.py

# Si tout est OK, vous devriez voir:
# 🎉 SETUP COMPLET ! L'intégration InfluxDB est prête.
```

### 3. Configuration Rapide

```bash
# Copier le template de configuration
cp .env.template .env

# Éditer la configuration
nano .env
```

## 🔧 Installation Manuelle Détaillée

### Étape 1: Dépendances Python

```bash
# Installer les dépendances InfluxDB
pip install influxdb-client==1.38.0
pip install pandas==2.1.4
pip install numpy==1.26.4
pip install python-decouple==3.8
pip install dj-database-url==3.0.0

# Ou utiliser requirements.txt
pip install -r requirements.txt
```

### Étape 2: Configuration Django

Ajoutez dans `vigileos/settings/base.py`:

```python
INSTALLED_APPS = [
    # ... autres apps
    'influxdb_integration',
]

# Configuration InfluxDB
INFLUXDB_CONFIG = {
    'url': config('INFLUXDB_URL', default='http://localhost:8086'),
    'token': config('INFLUXDB_TOKEN'),
    'org': config('INFLUXDB_ORG', default='vigileos'),
    'bucket': config('INFLUXDB_BUCKET', default='vigileos-metrics'),
    'timeout': config('INFLUXDB_TIMEOUT', default=10000, cast=int),
    'verify_ssl': config('INFLUXDB_VERIFY_SSL', default=True, cast=bool),
}
```

### Étape 3: Variables d'Environnement

Créez `.env`:

```bash
# InfluxDB Configuration
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=votre-token-ici
INFLUXDB_ORG=vigileos
INFLUXDB_BUCKET=vigileos-metrics
INFLUXDB_TIMEOUT=10000
INFLUXDB_VERIFY_SSL=True

# Django Configuration
DEBUG=False
SECRET_KEY=votre-secret-key-production
DATABASE_URL=postgresql://user:pass@localhost/vigileos
```

### Étape 4: Migrations

```bash
# Appliquer les migrations
python manage.py migrate

# Vérifier l'installation
python manage.py check_influxdb_status
```

## 🗄️ Installation InfluxDB

### Option 1: Docker (Recommandé)

```bash
# Créer docker-compose.yml
cat > docker-compose.yml << EOF
version: '3.8'
services:
  influxdb:
    image: influxdb:2.7
    container_name: vigileos-influxdb
    ports:
      - "8086:8086"
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=password123
      - DOCKER_INFLUXDB_INIT_ORG=vigileos
      - DOCKER_INFLUXDB_INIT_BUCKET=vigileos-metrics
      - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=your-super-secret-auth-token
    volumes:
      - influxdb-data:/var/lib/influxdb2
      - influxdb-config:/etc/influxdb2
    restart: unless-stopped

volumes:
  influxdb-data:
  influxdb-config:
EOF

# Démarrer InfluxDB
docker-compose up -d

# Vérifier le statut
docker-compose ps
```

### Option 2: Installation Native

#### Ubuntu/Debian

```bash
# Ajouter le repository InfluxDB
wget -qO- https://repos.influxdata.com/influxdb.key | sudo apt-key add -
echo "deb https://repos.influxdata.com/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/influxdb.list

# Installer InfluxDB
sudo apt update
sudo apt install influxdb2

# Démarrer le service
sudo systemctl start influxdb
sudo systemctl enable influxdb

# Configuration initiale
influx setup \
  --username admin \
  --password password123 \
  --org vigileos \
  --bucket vigileos-metrics \
  --force
```

#### CentOS/RHEL

```bash
# Ajouter le repository
cat > /etc/yum.repos.d/influxdb.repo << EOF
[influxdb]
name = InfluxDB Repository - RHEL
baseurl = https://repos.influxdata.com/rhel/\$releasever/\$basearch/stable/
enabled = 1
gpgcheck = 1
gpgkey = https://repos.influxdata.com/influxdb.key
EOF

# Installer
sudo yum install influxdb2

# Démarrer
sudo systemctl start influxdb
sudo systemctl enable influxdb
```

## 🔐 Configuration de Sécurité

### 1. Token d'Authentification

```bash
# Créer un token pour VIGILEOS
influx auth create \
  --org vigileos \
  --all-access \
  --description "VIGILEOS Application Token"

# Copier le token généré dans votre .env
```

### 2. Politiques de Rétention

```bash
# Créer des buckets avec rétention
influx bucket create \
  --name vigileos-metrics-realtime \
  --org vigileos \
  --retention 168h  # 7 jours

influx bucket create \
  --name vigileos-metrics-historical \
  --org vigileos \
  --retention 8760h  # 1 an
```

### 3. Utilisateurs et Permissions

```bash
# Créer un utilisateur lecture seule
influx user create \
  --name vigileos-readonly \
  --org vigileos

# Créer un token lecture seule
influx auth create \
  --org vigileos \
  --read-buckets \
  --user vigileos-readonly
```

## 🚀 Déploiement en Production

### 1. Configuration Nginx

```nginx
# /etc/nginx/sites-available/vigileos
server {
    listen 80;
    server_name votre-domaine.com;

    # Redirection HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name votre-domaine.com;

    # Certificats SSL
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Django
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # InfluxDB (optionnel, pour accès direct)
    location /influxdb/ {
        proxy_pass http://127.0.0.1:8086/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. Service Systemd pour Django

```ini
# /etc/systemd/system/vigileos.service
[Unit]
Description=VIGILEOS Django Application
After=network.target

[Service]
Type=exec
User=vigileos
Group=vigileos
WorkingDirectory=/opt/vigileos/backend
Environment=DJANGO_SETTINGS_MODULE=vigileos.settings.production
ExecStart=/opt/vigileos/venv/bin/python manage.py runserver 127.0.0.1:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Configuration Production

```python
# vigileos/settings/production.py
from .base import *

DEBUG = False
ALLOWED_HOSTS = ['votre-domaine.com', 'www.votre-domaine.com']

# Base de données PostgreSQL
DATABASES = {
    'default': dj_database_url.parse(config('DATABASE_URL'))
}

# InfluxDB Production
INFLUXDB_CONFIG = {
    'url': config('INFLUXDB_URL'),
    'token': config('INFLUXDB_TOKEN'),
    'org': config('INFLUXDB_ORG'),
    'bucket': config('INFLUXDB_BUCKET'),
    'timeout': 30000,  # 30 secondes
    'verify_ssl': True,
    'enable_gzip': True,
}

# Sécurité
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

## 📊 Monitoring et Maintenance

### 1. Health Checks

```bash
# Vérifier le statut InfluxDB
python manage.py check_influxdb_status

# Tester les APIs
curl -H "Authorization: Token your-token" \
     http://localhost:8000/api/influxdb/status/

# Vérifier les métriques
curl -H "Authorization: Token your-token" \
     http://localhost:8000/api/influxdb/dashboard/
```

### 2. Maintenance Automatique

```bash
# Ajouter au crontab
crontab -e

# Nettoyage quotidien (2h du matin)
0 2 * * * /opt/vigileos/venv/bin/python /opt/vigileos/backend/manage.py cleanup_influxdb_data --days 30

# Vérification de santé (toutes les heures)
0 * * * * /opt/vigileos/venv/bin/python /opt/vigileos/backend/manage.py check_influxdb_status
```

### 3. Sauvegarde

```bash
#!/bin/bash
# backup_influxdb.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/influxdb"

# Créer le répertoire de sauvegarde
mkdir -p $BACKUP_DIR

# Sauvegarder InfluxDB
influx backup \
  --org vigileos \
  --token $INFLUXDB_TOKEN \
  $BACKUP_DIR/backup_$DATE

# Compresser
tar -czf $BACKUP_DIR/backup_$DATE.tar.gz $BACKUP_DIR/backup_$DATE
rm -rf $BACKUP_DIR/backup_$DATE

# Nettoyer les anciennes sauvegardes (garder 7 jours)
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +7 -delete
```

## 🔧 Optimisation des Performances

### 1. Configuration InfluxDB

```toml
# /etc/influxdb/config.toml
[http]
  bind-address = ":8086"
  max-body-size = "25MB"
  max-concurrent-requests = 0
  max-enqueued-requests = 0

[storage-engine]
  max-concurrent-compactions = 3
  max-index-log-file-size = "1MB"
  series-id-set-cache-size = 100

[query]
  max-memory-bytes = 0
  query-concurrency = 10
  query-queue-size = 10
```

### 2. Optimisation Django

```python
# settings/production.py

# Cache Redis pour les requêtes fréquentes
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Configuration InfluxDB optimisée
INFLUXDB_CONFIG = {
    'url': config('INFLUXDB_URL'),
    'token': config('INFLUXDB_TOKEN'),
    'org': config('INFLUXDB_ORG'),
    'bucket': config('INFLUXDB_BUCKET'),
    'timeout': 30000,
    'verify_ssl': True,
    'enable_gzip': True,
    'batch_size': 5000,  # Écriture en lot
    'flush_interval': 10000,  # 10 secondes
}
```

## 🐛 Dépannage

### Problèmes Courants

#### 1. Connexion InfluxDB Échouée

```bash
# Vérifier le service
sudo systemctl status influxdb

# Vérifier les logs
sudo journalctl -u influxdb -f

# Tester la connexion
curl -I http://localhost:8086/ping
```

#### 2. Token Invalide

```bash
# Lister les tokens
influx auth list --org vigileos

# Créer un nouveau token
influx auth create --org vigileos --all-access
```

#### 3. Bucket Introuvable

```bash
# Lister les buckets
influx bucket list --org vigileos

# Créer le bucket manquant
influx bucket create --name vigileos-metrics --org vigileos
```

#### 4. Performances Lentes

```bash
# Vérifier l'utilisation des ressources
htop

# Analyser les requêtes lentes
influx query --org vigileos 'SHOW QUERIES'

# Optimiser la base
python optimize_influxdb.py
```

### Logs et Debugging

```python
# settings/production.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'influxdb_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/vigileos/influxdb.log',
        },
    },
    'loggers': {
        'influxdb_integration': {
            'handlers': ['influxdb_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## 📈 Monitoring Avancé

### 1. Métriques Système

```bash
# Installer Telegraf pour collecter les métriques système
sudo apt install telegraf

# Configuration Telegraf
cat > /etc/telegraf/telegraf.conf << EOF
[agent]
  interval = "10s"

[[outputs.influxdb_v2]]
  urls = ["http://localhost:8086"]
  token = "$INFLUXDB_TOKEN"
  organization = "vigileos"
  bucket = "system-metrics"

[[inputs.cpu]]
[[inputs.disk]]
[[inputs.mem]]
[[inputs.net]]
EOF

sudo systemctl start telegraf
sudo systemctl enable telegraf
```

### 2. Dashboards Grafana

```bash
# Installer Grafana
sudo apt install grafana

# Configurer la source de données InfluxDB
# URL: http://localhost:8086
# Organization: vigileos
# Token: votre-token
# Default Bucket: vigileos-metrics
```

## 🎯 Checklist de Déploiement

### Pré-déploiement

- [ ] InfluxDB installé et configuré
- [ ] Tokens d'authentification créés
- [ ] Buckets configurés avec rétention
- [ ] Variables d'environnement définies
- [ ] Tests de connexion réussis

### Déploiement

- [ ] Code déployé en production
- [ ] Migrations appliquées
- [ ] Services redémarrés
- [ ] Health checks passés
- [ ] APIs testées

### Post-déploiement

- [ ] Monitoring configuré
- [ ] Sauvegardes programmées
- [ ] Alertes configurées
- [ ] Documentation mise à jour
- [ ] Équipe formée

## 📞 Support

En cas de problème:

1. Consultez les logs: `/var/log/vigileos/`
2. Vérifiez le statut: `python manage.py check_influxdb_status`
3. Testez les APIs: `curl -H "Authorization: Token ..." ...`
4. Consultez la documentation InfluxDB: https://docs.influxdata.com/

---

**🎉 Félicitations ! Votre intégration InfluxDB est maintenant déployée et prête pour la production.**