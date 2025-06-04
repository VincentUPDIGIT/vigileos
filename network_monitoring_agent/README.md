# Network Monitoring Agent

A comprehensive cross-platform network monitoring agent with multi-client authentication, secure tunneling, and real-time metrics collection.

## Features

### 🌐 Cross-Platform Support
- **Linux** (systemd service)
- **Windows** (Windows Service)
- **macOS** (launchd service)

### 📊 Monitoring Capabilities
- **SNMP** monitoring for network devices
- **SSH** remote command execution
- **Web scraping** for device interfaces
- **REST API** integration
- **System metrics** collection

### 🔐 Security Features
- **Multi-client authentication** (JWT, OAuth2, mTLS, API keys)
- **End-to-end encryption** for data transmission
- **Secure tunneling** (WireGuard, SSH, OpenVPN)
- **Role-based access control**

### 🚀 Advanced Features
- **Auto-discovery** of network devices
- **Real-time metrics** collection and aggregation
- **Backend synchronization** with retry and offline storage
- **Tunnel management** for secure remote access
- **Performance monitoring** and alerting

## Quick Start

### Installation

1. **Download and extract** the agent:
```bash
git clone https://github.com/company/network-monitoring-agent.git
cd network-monitoring-agent
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Run installation script**:
```bash
# Linux/macOS (requires sudo)
sudo python3 scripts/install.py

# Windows (requires Administrator)
python scripts/install.py
```

### Configuration

Edit the configuration file:
- **Linux/macOS**: `/etc/network-agent/config.json`
- **Windows**: `C:\ProgramData\NetworkAgent\config.json`

```json
{
  "agent": {
    "client_id": "your-client-id",
    "auto_discovery": true,
    "discovery_networks": ["192.168.1.0/24"]
  },
  "backend": {
    "base_url": "https://your-backend.com",
    "auth_token": "your-auth-token"
  }
}
```

### Service Management

#### Linux (systemd)
```bash
sudo systemctl start network-monitoring-agent
sudo systemctl enable network-monitoring-agent
sudo systemctl status network-monitoring-agent
```

#### Windows
```cmd
sc start NetworkMonitoringAgent
sc config NetworkMonitoringAgent start= auto
sc query NetworkMonitoringAgent
```

#### macOS (launchd)
```bash
sudo launchctl start com.company.network-monitoring-agent
sudo launchctl enable system/com.company.network-monitoring-agent
```

## Architecture

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Main Agent    │────│  Auth Manager   │────│ Metrics Collector│
│  (Orchestrator) │    │ (Multi-client)  │    │  (SNMP/SSH/Web) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐    ┌─────────────────┐
         │──────────────│ Tunnel Manager  │────│ Backend Sync    │
         │              │ (WG/SSH/OpenVPN)│    │ (HTTP/Offline)  │
         │              └─────────────────┘    └─────────────────┘
         │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Platform Layer  │────│   Utilities     │────│   API Clients   │
│ (Linux/Win/Mac) │    │ (Crypto/Logger) │    │ (SNMP/SSH/REST) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Models

- **Device**: Network device configuration and credentials
- **Metric**: Time-series data points with metadata
- **Client**: Multi-tenant client configuration and permissions

### Platform Abstraction

The agent uses a factory pattern to provide platform-specific implementations:

```python
from platforms.platform_factory import PlatformFactory

platform = PlatformFactory.get_platform()
metrics = await platform.get_system_metrics()
```

## Configuration Reference

### Agent Configuration

```json
{
  "agent": {
    "name": "network-monitoring-agent",
    "client_id": "unique-client-identifier",
    "log_level": "INFO",
    "auto_discovery": true,
    "discovery_networks": ["192.168.1.0/24", "10.0.0.0/24"],
    "max_devices": 1000
  }
}
```

### Authentication Configuration

```json
{
  "auth": {
    "method": "jwt",
    "token_expiry": 3600,
    "enable_multi_client": true,
    "allowed_clients": ["client1", "client2"]
  }
}
```

### Collection Configuration

```json
{
  "collection": {
    "interval": 60,
    "timeout": 30,
    "retry_attempts": 3,
    "enabled_collectors": ["snmp", "ssh", "web", "api", "system"],
    "max_concurrent": 50
  }
}
```

### Backend Configuration

```json
{
  "backend": {
    "base_url": "https://api.monitoring.example.com",
    "auth_token": "your-jwt-token",
    "verify_ssl": true,
    "compression": true,
    "sync_interval": 60,
    "offline_storage": true
  }
}
```

### Tunnel Configuration

```json
{
  "tunnels": {
    "enable_wireguard": true,
    "enable_ssh": true,
    "enable_openvpn": false,
    "auto_cleanup": true,
    "max_tunnels": 10
  }
}
```

## Device Configuration

### SNMP Device

```python
from models.device import Device, DeviceType, SNMPConfig

device = Device(
    device_id="router_001",
    name="Main Router",
    device_type=DeviceType.ROUTER,
    ip_address="192.168.1.1",
    snmp_config=SNMPConfig(
        community="public",
        version="2c",
        port=161
    )
)
```

### SSH Device

```python
from models.device import SSHConfig

device = Device(
    device_id="server_001",
    name="Linux Server",
    device_type=DeviceType.SERVER,
    ip_address="192.168.1.100",
    ssh_config=SSHConfig(
        username="admin",
        password="secure_password",
        port=22
    )
)
```

### Web Interface Device

```python
from models.device import WebConfig

device = Device(
    device_id="ap_001",
    name="Access Point",
    device_type=DeviceType.ACCESS_POINT,
    ip_address="192.168.1.50",
    web_config=WebConfig(
        base_url="https://192.168.1.50",
        username="admin",
        password="admin"
    )
)
```

## API Usage

### Adding Devices Programmatically

```python
import asyncio
from agent.main_agent import NetworkMonitoringAgent

async def add_device():
    agent = NetworkMonitoringAgent()
    await agent.initialize_components()
    
    device = Device(
        device_id="new_device",
        name="New Device",
        device_type=DeviceType.SWITCH,
        ip_address="192.168.1.200"
    )
    
    agent.metrics_collector.add_device(device)
```

### Creating Tunnels

```python
# WireGuard tunnel
tunnel_id = await agent.tunnel_manager.create_wireguard_tunnel(
    name="remote_site",
    remote_endpoint="vpn.example.com:51820",
    public_key="remote_public_key",
    allowed_ips=["10.0.0.0/24"]
)

# SSH tunnel
tunnel_id = await agent.tunnel_manager.create_ssh_tunnel(
    name="ssh_tunnel",
    ssh_host="jump.example.com",
    ssh_port=22,
    local_port=8080,
    remote_host="internal.example.com",
    remote_port=80,
    username="tunnel_user",
    private_key="ssh_private_key"
)
```

## Monitoring and Alerting

### Metric Types

- **Performance**: CPU, memory, disk usage
- **Network**: Interface statistics, bandwidth, latency
- **System**: Uptime, temperature, power status
- **Security**: Failed logins, firewall events
- **Application**: Service-specific metrics

### Threshold Configuration

```python
from models.metric import Metric, MetricThreshold

metric = Metric(
    device_id="server_001",
    name="cpu_usage",
    value=85.5,
    unit="percent"
)

metric.set_threshold(
    warning_max=80.0,
    critical_max=90.0
)
```

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

**Linux/macOS:**
```bash
# Check service status
sudo systemctl status network-monitoring-agent

# Check logs
sudo journalctl -u network-monitoring-agent -f

# Check configuration
sudo python3 -m src.agent.main_agent --config /etc/network-agent/config.json
```

**Windows:**
```cmd
# Check service status
sc query NetworkMonitoringAgent

# Check event logs
eventvwr.msc

# Test configuration
python -m src.agent.main_agent --config "C:\ProgramData\NetworkAgent\config.json"
```

#### 2. Permission Issues

**Linux/macOS:**
```bash
# Fix ownership
sudo chown -R network-agent:network-agent /var/lib/network-agent
sudo chown -R network-agent:network-agent /var/log/network-agent

# Fix permissions
sudo chmod 755 /var/lib/network-agent
sudo chmod 755 /var/log/network-agent
```

#### 3. Network Connectivity

```bash
# Test backend connectivity
curl -I https://your-backend.com/health

# Test device connectivity
ping 192.168.1.1
telnet 192.168.1.1 161  # SNMP
telnet 192.168.1.1 22   # SSH
```

#### 4. SNMP Issues

```bash
# Test SNMP manually
snmpwalk -v2c -c public 192.168.1.1 1.3.6.1.2.1.1.1.0

# Check SNMP service
sudo systemctl status snmpd  # Linux
```

### Validation Tools

#### Installation Validation
```bash
python3 scripts/validate_installation.py
```

#### Comprehensive Testing
```bash
python3 scripts/run_tests.py
```

#### Manual Testing
```bash
# Test agent directly
python3 main.py --config config/default_config.json

# Test specific components
python3 -c "
from src.platforms.platform_factory import PlatformFactory
platform = PlatformFactory.get_platform()
print(f'Platform: {platform.platform_name}')
"
```

## Development

### Project Structure

```
network_monitoring_agent/
├── src/
│   ├── agent/           # Core agent components
│   ├── models/          # Data models
│   ├── platforms/       # Platform-specific implementations
│   ├── utils/           # Utilities and helpers
│   ├── apis/            # API clients
│   └── services/        # System service implementations
├── config/              # Configuration files
├── scripts/             # Installation and utility scripts
├── tests/               # Test suite
├── requirements.txt     # Python dependencies
└── main.py             # Main entry point
```

### Adding New Platforms

1. Create platform implementation:
```python
# src/platforms/new_platform.py
from .base_platform import BasePlatform

class NewPlatform(BasePlatform):
    platform_name = "new_platform"
    
    async def get_system_metrics(self):
        # Implementation
        pass
```

2. Register in factory:
```python
# src/platforms/platform_factory.py
def get_platform():
    if platform.system().lower() == "new_os":
        from .new_platform import NewPlatform
        return NewPlatform()
```

### Adding New Collectors

1. Create collector implementation:
```python
# src/apis/new_collector.py
class NewCollector:
    async def collect_metrics(self, device):
        # Implementation
        pass
```

2. Register in metrics collector:
```python
# src/agent/metrics_collector.py
self.collectors['new_protocol'] = NewCollector()
```

## Security Considerations

### Network Security
- Use encrypted tunnels (WireGuard/SSH) for remote access
- Implement proper firewall rules
- Use strong authentication credentials
- Enable SSL/TLS verification for backend connections

### Data Security
- All sensitive data is encrypted at rest
- Credentials are stored securely using platform keyring
- Regular key rotation is supported
- Audit logging for security events

### Access Control
- Multi-client authentication with role-based permissions
- IP-based access restrictions
- Rate limiting for API endpoints
- Secure token management

## Performance Tuning

### Collection Optimization
```json
{
  "collection": {
    "interval": 60,           # Increase for less frequent collection
    "max_concurrent": 20,     # Reduce for lower resource usage
    "timeout": 10,            # Reduce for faster timeouts
    "batch_size": 50          # Adjust based on backend capacity
  }
}
```

### Memory Management
```json
{
  "performance": {
    "max_memory_usage_mb": 256,
    "gc_threshold": 1000,
    "connection_pool_size": 10
  }
}
```

### Backend Sync Optimization
```json
{
  "backend": {
    "sync_interval": 300,     # Less frequent sync
    "batch_size": 200,        # Larger batches
    "compression": true,      # Enable compression
    "offline_storage": true   # Enable offline storage
  }
}
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Run validation scripts for diagnostics

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## Changelog

### Version 1.0.0
- Initial release
- Cross-platform support (Linux, Windows, macOS)
- Multi-protocol monitoring (SNMP, SSH, Web, REST API)
- Secure tunneling support
- Multi-client authentication
- Real-time metrics collection
- Backend synchronization
- Auto-discovery functionality