"""
Main network monitoring agent orchestrator.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from agent.auth_manager import AuthManager, AuthMethod
from agent.metrics_collector import MetricsCollector, CollectionConfig
from agent.tunnel_manager import TunnelManager
from agent.backend_sync import BackendSync, BackendConfig
from models.device import Device, DeviceType
from models.client import Client, ClientType
from platforms.platform_factory import PlatformFactory
from utils.logger import setup_application_logging
from utils.platform_utils import PlatformPaths, PlatformUtils
from utils.network_scanner import NetworkScanner


class AgentStatus:
    """Agent status tracking."""
    
    def __init__(self):
        self.started_at = datetime.utcnow()
        self.is_running = False
        self.components = {
            'auth_manager': False,
            'metrics_collector': False,
            'tunnel_manager': False,
            'backend_sync': False
        }
        self.stats = {
            'devices_monitored': 0,
            'metrics_collected': 0,
            'tunnels_active': 0,
            'last_sync': None
        }


class NetworkMonitoringAgent:
    """
    Main network monitoring agent.
    
    Orchestrates all components: authentication, metrics collection,
    tunnel management, and backend synchronization.
    """
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize the network monitoring agent.
        
        Args:
            config_file: Path to configuration file
        """
        # Setup logging first
        self.logger = setup_application_logging("network_agent")
        
        # Load configuration
        self.config = self._load_config(config_file)
        
        # Platform detection
        self.platform = PlatformFactory.get_platform()
        self.logger.info(f"Running on {self.platform.platform_name}")
        
        # Status tracking
        self.status = AgentStatus()
        
        # Core components
        self.auth_manager: Optional[AuthManager] = None
        self.metrics_collector: Optional[MetricsCollector] = None
        self.tunnel_manager: Optional[TunnelManager] = None
        self.backend_sync: Optional[BackendSync] = None
        self.network_scanner: Optional[NetworkScanner] = None
        
        # Runtime state
        self.shutdown_event = asyncio.Event()
        self.main_task: Optional[asyncio.Task] = None
        
        self.logger.info("NetworkMonitoringAgent initialized")
    
    def _load_config(self, config_file: Optional[Path] = None) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        default_config = {
            'agent': {
                'name': 'network-monitoring-agent',
                'client_id': 'default-client',
                'log_level': 'INFO',
                'data_dir': str(PlatformPaths.get_data_dir()),
                'auto_discovery': True,
                'discovery_networks': []
            },
            'auth': {
                'method': 'jwt',
                'token_expiry': 3600,
                'enable_multi_client': True
            },
            'collection': {
                'interval': 60,
                'timeout': 30,
                'retry_attempts': 3,
                'batch_size': 100,
                'enabled_collectors': ['snmp', 'ssh', 'web', 'api', 'system']
            },
            'backend': {
                'base_url': 'https://api.monitoring.example.com',
                'auth_token': None,
                'api_key': None,
                'timeout': 30,
                'verify_ssl': True,
                'compression': True,
                'batch_size': 100,
                'sync_interval': 60
            },
            'tunnels': {
                'enable_wireguard': True,
                'enable_ssh': True,
                'enable_openvpn': False,
                'auto_cleanup': True
            }
        }
        
        if config_file and config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    if config_file.suffix.lower() in ['.yaml', '.yml']:
                        import yaml
                        file_config = yaml.safe_load(f)
                    else:
                        file_config = json.load(f)
                
                # Merge with defaults
                self._deep_merge(default_config, file_config)
                self.logger.info(f"Configuration loaded from {config_file}")
                
            except Exception as e:
                self.logger.warning(f"Failed to load config file {config_file}: {e}")
        
        return default_config
    
    def _deep_merge(self, base: Dict, update: Dict):
        """Deep merge configuration dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    async def initialize_components(self):
        """Initialize all agent components."""
        try:
            self.logger.info("Initializing agent components...")
            
            # Initialize authentication manager
            auth_config = self.config.get('auth', {})
            self.auth_manager = AuthManager(auth_config)
            self.status.components['auth_manager'] = True
            self.logger.info("Authentication manager initialized")
            
            # Initialize metrics collector
            collection_config = CollectionConfig(**self.config.get('collection', {}))
            self.metrics_collector = MetricsCollector(collection_config)
            self.status.components['metrics_collector'] = True
            self.logger.info("Metrics collector initialized")
            
            # Initialize tunnel manager
            self.tunnel_manager = TunnelManager()
            self.status.components['tunnel_manager'] = True
            self.logger.info("Tunnel manager initialized")
            
            # Initialize backend sync
            backend_config = BackendConfig(**self.config.get('backend', {}))
            backend_config.client_id = self.config['agent']['client_id']
            self.backend_sync = BackendSync(backend_config)
            self.status.components['backend_sync'] = True
            self.logger.info("Backend sync initialized")
            
            # Initialize network scanner
            self.network_scanner = NetworkScanner()
            self.logger.info("Network scanner initialized")
            
            # Setup callbacks
            self._setup_callbacks()
            
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Component initialization failed: {e}")
            raise
    
    def _setup_callbacks(self):
        """Setup inter-component callbacks."""
        # Metrics collection callback -> Backend sync
        def on_metrics_collected(result):
            if result.metrics:
                self.backend_sync.add_metrics(result.metrics)
                self.status.stats['metrics_collected'] += len(result.metrics)
        
        self.metrics_collector.add_collection_callback(on_metrics_collected)
        
        # Backend command callback
        def on_backend_command(command):
            asyncio.create_task(self._handle_backend_command(command))
        
        self.backend_sync.add_command_callback(on_backend_command)
    
    async def _handle_backend_command(self, command: Dict[str, Any]):
        """Handle commands from backend."""
        try:
            command_type = command.get('type')
            self.logger.info(f"Handling backend command: {command_type}")
            
            if command_type == 'add_device':
                await self._handle_add_device_command(command)
            elif command_type == 'remove_device':
                await self._handle_remove_device_command(command)
            elif command_type == 'create_tunnel':
                await self._handle_create_tunnel_command(command)
            elif command_type == 'destroy_tunnel':
                await self._handle_destroy_tunnel_command(command)
            elif command_type == 'update_config':
                await self._handle_update_config_command(command)
            else:
                self.logger.warning(f"Unknown command type: {command_type}")
        
        except Exception as e:
            self.logger.error(f"Command handling failed: {e}")
    
    async def _handle_add_device_command(self, command: Dict[str, Any]):
        """Handle add device command."""
        device_data = command.get('device', {})
        device = Device.from_dict(device_data)
        
        if device.is_valid():
            self.metrics_collector.add_device(device)
            self.logger.info(f"Added device: {device.device_id}")
        else:
            self.logger.error(f"Invalid device configuration: {device.validate()}")
    
    async def _handle_remove_device_command(self, command: Dict[str, Any]):
        """Handle remove device command."""
        device_id = command.get('device_id')
        if device_id:
            success = self.metrics_collector.remove_device(device_id)
            if success:
                self.logger.info(f"Removed device: {device_id}")
            else:
                self.logger.warning(f"Device not found: {device_id}")
    
    async def _handle_create_tunnel_command(self, command: Dict[str, Any]):
        """Handle create tunnel command."""
        tunnel_config = command.get('tunnel_config', {})
        tunnel_type = tunnel_config.get('type', 'wireguard')
        
        if tunnel_type == 'wireguard':
            tunnel_id = await self.tunnel_manager.create_wireguard_tunnel(
                name=tunnel_config.get('name'),
                remote_endpoint=tunnel_config.get('remote_endpoint'),
                public_key=tunnel_config.get('public_key'),
                allowed_ips=tunnel_config.get('allowed_ips', [])
            )
            self.logger.info(f"Created WireGuard tunnel: {tunnel_id}")
        elif tunnel_type == 'ssh':
            tunnel_id = await self.tunnel_manager.create_ssh_tunnel(
                name=tunnel_config.get('name'),
                ssh_host=tunnel_config.get('ssh_host'),
                ssh_port=tunnel_config.get('ssh_port', 22),
                local_port=tunnel_config.get('local_port'),
                remote_host=tunnel_config.get('remote_host'),
                remote_port=tunnel_config.get('remote_port'),
                username=tunnel_config.get('username'),
                password=tunnel_config.get('password')
            )
            self.logger.info(f"Created SSH tunnel: {tunnel_id}")
    
    async def _handle_destroy_tunnel_command(self, command: Dict[str, Any]):
        """Handle destroy tunnel command."""
        tunnel_id = command.get('tunnel_id')
        if tunnel_id:
            success = await self.tunnel_manager.destroy_tunnel(tunnel_id)
            if success:
                self.logger.info(f"Destroyed tunnel: {tunnel_id}")
            else:
                self.logger.warning(f"Failed to destroy tunnel: {tunnel_id}")
    
    async def _handle_update_config_command(self, command: Dict[str, Any]):
        """Handle configuration update command."""
        new_config = command.get('config', {})
        
        # Update collection interval if specified
        if 'collection_interval' in new_config:
            self.metrics_collector.config.interval = new_config['collection_interval']
            self.logger.info(f"Updated collection interval: {new_config['collection_interval']}")
        
        # Update sync interval if specified
        if 'sync_interval' in new_config:
            self.backend_sync.config.sync_interval = new_config['sync_interval']
            self.logger.info(f"Updated sync interval: {new_config['sync_interval']}")
    
    async def discover_devices(self):
        """Discover devices on local networks."""
        if not self.config['agent'].get('auto_discovery', True):
            return
        
        try:
            self.logger.info("Starting device discovery...")
            
            # Get networks to scan
            networks = self.config['agent'].get('discovery_networks', [])
            if not networks:
                networks = self.network_scanner.get_local_networks()
            
            discovered_devices = []
            for network in networks:
                self.logger.info(f"Scanning network: {network}")
                devices = await self.network_scanner.scan_subnet_for_devices(network)
                discovered_devices.extend(devices)
            
            # Convert discovered devices to Device objects
            for discovered in discovered_devices:
                device = Device(
                    device_id=discovered.ip_address.replace('.', '_'),
                    name=discovered.hostname or f"Device_{discovered.ip_address}",
                    device_type=self._map_device_type(discovered.device_type),
                    ip_address=discovered.ip_address,
                    mac_address=discovered.mac_address,
                    hostname=discovered.hostname,
                    vendor=discovered.vendor
                )
                
                # Configure monitoring based on available services
                if 161 in discovered.open_ports:  # SNMP
                    from models.device import SNMPConfig
                    device.snmp_config = SNMPConfig(
                        community=discovered.snmp_community or "public"
                    )
                
                if 22 in discovered.open_ports:  # SSH
                    from models.device import SSHConfig
                    device.ssh_config = SSHConfig(
                        username="admin"  # Default, should be configured
                    )
                
                if any(port in discovered.open_ports for port in [80, 443, 8080, 8443]):
                    from models.device import WebConfig
                    protocol = "https" if 443 in discovered.open_ports else "http"
                    port = 443 if 443 in discovered.open_ports else 80
                    device.web_config = WebConfig(
                        base_url=f"{protocol}://{discovered.ip_address}:{port}"
                    )
                
                # Add device to monitoring
                if device.get_available_protocols():
                    self.metrics_collector.add_device(device)
                    self.logger.info(f"Added discovered device: {device.device_id}")
            
            self.logger.info(f"Device discovery completed: {len(discovered_devices)} devices found")
            
        except Exception as e:
            self.logger.error(f"Device discovery failed: {e}")
    
    def _map_device_type(self, discovered_type: str) -> DeviceType:
        """Map discovered device type to DeviceType enum."""
        type_mapping = {
            'router': DeviceType.ROUTER,
            'switch': DeviceType.SWITCH,
            'access_point': DeviceType.ACCESS_POINT,
            'firewall': DeviceType.FIREWALL,
            'server': DeviceType.SERVER,
            'network_device': DeviceType.ROUTER  # Default for unknown network devices
        }
        
        return type_mapping.get(discovered_type, DeviceType.UNKNOWN)
    
    async def start(self):
        """Start the monitoring agent."""
        try:
            self.logger.info("Starting Network Monitoring Agent...")
            
            # Initialize components
            await self.initialize_components()
            
            # Test backend connection
            if await self.backend_sync.test_connection():
                self.logger.info("Backend connection successful")
            else:
                self.logger.warning("Backend connection failed - running in offline mode")
            
            # Discover devices
            await self.discover_devices()
            
            # Start components
            await self.metrics_collector.start_collection()
            await self.backend_sync.start_periodic_sync()
            
            self.status.is_running = True
            self.logger.info("Network Monitoring Agent started successfully")
            
            # Setup signal handlers
            self._setup_signal_handlers()
            
            # Start main loop
            self.main_task = asyncio.create_task(self._main_loop())
            await self.main_task
            
        except Exception as e:
            self.logger.error(f"Agent startup failed: {e}")
            raise
    
    async def stop(self):
        """Stop the monitoring agent."""
        try:
            self.logger.info("Stopping Network Monitoring Agent...")
            
            # Signal shutdown
            self.shutdown_event.set()
            
            # Stop components
            if self.metrics_collector:
                await self.metrics_collector.stop_collection()
            
            if self.backend_sync:
                await self.backend_sync.stop_periodic_sync()
                await self.backend_sync.close_session()
            
            # Cancel main task
            if self.main_task and not self.main_task.done():
                self.main_task.cancel()
                try:
                    await self.main_task
                except asyncio.CancelledError:
                    pass
            
            self.status.is_running = False
            self.logger.info("Network Monitoring Agent stopped")
            
        except Exception as e:
            self.logger.error(f"Agent shutdown failed: {e}")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    async def _main_loop(self):
        """Main agent loop."""
        while not self.shutdown_event.is_set():
            try:
                # Update status statistics
                await self._update_status_stats()
                
                # Periodic maintenance
                await self._periodic_maintenance()
                
                # Wait before next iteration
                await asyncio.sleep(30)  # 30 second status update interval
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Main loop error: {e}")
                await asyncio.sleep(30)
    
    async def _update_status_stats(self):
        """Update agent status statistics."""
        try:
            if self.metrics_collector:
                self.status.stats['devices_monitored'] = len(self.metrics_collector.devices)
            
            if self.tunnel_manager:
                tunnels = await self.tunnel_manager.list_tunnels()
                self.status.stats['tunnels_active'] = len([t for t in tunnels if t.status.value == 'active'])
            
            if self.backend_sync and self.backend_sync.last_sync:
                self.status.stats['last_sync'] = self.backend_sync.last_sync.isoformat()
        
        except Exception as e:
            self.logger.debug(f"Status update failed: {e}")
    
    async def _periodic_maintenance(self):
        """Perform periodic maintenance tasks."""
        try:
            # Cleanup inactive tunnels
            if self.tunnel_manager:
                cleaned = await self.tunnel_manager.cleanup_inactive_tunnels()
                if cleaned > 0:
                    self.logger.info(f"Cleaned up {cleaned} inactive tunnels")
            
            # Log status every 5 minutes
            uptime = datetime.utcnow() - self.status.started_at
            if uptime.total_seconds() % 300 < 30:  # Every 5 minutes
                self.logger.info(f"Agent status: {self.get_status_summary()}")
        
        except Exception as e:
            self.logger.debug(f"Maintenance task failed: {e}")
    
    def get_status_summary(self) -> str:
        """Get agent status summary."""
        uptime = datetime.utcnow() - self.status.started_at
        return (f"Uptime: {uptime}, "
                f"Devices: {self.status.stats['devices_monitored']}, "
                f"Tunnels: {self.status.stats['tunnels_active']}, "
                f"Running: {self.status.is_running}")
    
    def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed agent status."""
        uptime = datetime.utcnow() - self.status.started_at
        
        status = {
            'agent': {
                'name': self.config['agent']['name'],
                'version': '1.0.0',
                'platform': self.platform.platform_name,
                'started_at': self.status.started_at.isoformat(),
                'uptime_seconds': uptime.total_seconds(),
                'is_running': self.status.is_running
            },
            'components': self.status.components.copy(),
            'statistics': self.status.stats.copy()
        }
        
        # Add component-specific stats
        if self.metrics_collector:
            status['metrics_collector'] = self.metrics_collector.get_collection_stats()
        
        if self.tunnel_manager:
            status['tunnel_manager'] = self.tunnel_manager.get_tunnel_manager_stats()
        
        if self.backend_sync:
            status['backend_sync'] = self.backend_sync.get_sync_stats()
        
        return status


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Network Monitoring Agent')
    parser.add_argument('--config', type=Path, help='Configuration file path')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--status', action='store_true', help='Show agent status')
    
    args = parser.parse_args()
    
    if args.status:
        # Show status (would connect to running agent)
        print("Agent status checking not implemented yet")
        return
    
    # Create and start agent
    agent = NetworkMonitoringAgent(args.config)
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        print(f"Agent failed: {e}")
        sys.exit(1)
    finally:
        await agent.stop()


if __name__ == '__main__':
    asyncio.run(main())