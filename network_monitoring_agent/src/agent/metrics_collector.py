"""
Cross-platform metrics collector for network devices and system monitoring.
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from platforms.platform_factory import PlatformFactory
from models.device import Device, DeviceType
from models.metric import Metric, MetricType
from apis.snmp_client import SNMPClient
from apis.ssh_client import SSHClient
from apis.web_scraper import WebScraper
from apis.rest_api_client import RestAPIClient
from utils.platform_utils import PlatformUtils


class CollectionStatus(Enum):
    """Metric collection status."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"
    UNREACHABLE = "unreachable"


@dataclass
class CollectionResult:
    """Result of a metric collection operation."""
    device_id: str
    metrics: List[Metric]
    status: CollectionStatus
    timestamp: datetime
    duration: float
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        data['timestamp'] = self.timestamp.isoformat()
        data['metrics'] = [metric.to_dict() for metric in self.metrics]
        return data


@dataclass
class CollectionConfig:
    """Configuration for metric collection."""
    interval: int = 60  # seconds
    timeout: int = 30   # seconds
    retry_attempts: int = 3
    retry_delay: int = 5  # seconds
    batch_size: int = 10
    enabled_collectors: List[str] = None
    
    def __post_init__(self):
        if self.enabled_collectors is None:
            self.enabled_collectors = ['snmp', 'ssh', 'web', 'api', 'system']


class MetricsCollector:
    """
    Cross-platform metrics collector.
    
    Collects metrics from various sources:
    - SNMP devices
    - SSH-accessible devices
    - Web interfaces
    - REST APIs
    - Local system metrics
    """
    
    def __init__(self, config: CollectionConfig = None):
        """
        Initialize the metrics collector.
        
        Args:
            config: Collection configuration
        """
        self.config = config or CollectionConfig()
        self.logger = logging.getLogger(__name__)
        
        # Platform-specific implementation
        self.platform = PlatformFactory.get_platform()
        
        # API clients
        self.snmp_client = SNMPClient()
        self.ssh_client = SSHClient()
        self.web_scraper = WebScraper()
        self.rest_client = RestAPIClient()
        
        # Collection state
        self.is_running = False
        self.collection_task = None
        self.devices: Dict[str, Device] = {}
        self.collection_history: List[CollectionResult] = []
        
        # Metrics cache
        self.metrics_cache: Dict[str, List[Metric]] = {}
        self.cache_ttl = 300  # 5 minutes
        
        # Collection callbacks
        self.collection_callbacks: List[Callable[[CollectionResult], None]] = []
        
        self.logger.info(f"MetricsCollector initialized on {self.platform.platform_name}")
    
    def add_device(self, device: Device):
        """Add a device to monitor."""
        self.devices[device.device_id] = device
        self.logger.info(f"Added device {device.device_id} ({device.device_type.value})")
    
    def remove_device(self, device_id: str) -> bool:
        """Remove a device from monitoring."""
        if device_id in self.devices:
            del self.devices[device_id]
            # Clear cached metrics
            if device_id in self.metrics_cache:
                del self.metrics_cache[device_id]
            self.logger.info(f"Removed device {device_id}")
            return True
        return False
    
    def get_device(self, device_id: str) -> Optional[Device]:
        """Get device by ID."""
        return self.devices.get(device_id)
    
    def list_devices(self) -> List[Device]:
        """List all monitored devices."""
        return list(self.devices.values())
    
    def add_collection_callback(self, callback: Callable[[CollectionResult], None]):
        """Add a callback to be called after each collection."""
        self.collection_callbacks.append(callback)
    
    async def collect_snmp_metrics(self, device: Device) -> List[Metric]:
        """
        Collect SNMP metrics from a device.
        
        Args:
            device: Device to collect from
            
        Returns:
            List[Metric]: Collected metrics
        """
        metrics = []
        
        try:
            if not device.snmp_config:
                return metrics
            
            # Connect to SNMP device
            await self.snmp_client.connect(
                host=device.ip_address,
                community=device.snmp_config.get('community', 'public'),
                version=device.snmp_config.get('version', '2c'),
                port=device.snmp_config.get('port', 161)
            )
            
            # Collect system information
            system_metrics = await self._collect_snmp_system_metrics(device)
            metrics.extend(system_metrics)
            
            # Collect interface metrics
            interface_metrics = await self._collect_snmp_interface_metrics(device)
            metrics.extend(interface_metrics)
            
            # Collect device-specific metrics
            if device.device_type == DeviceType.ROUTER:
                routing_metrics = await self._collect_snmp_routing_metrics(device)
                metrics.extend(routing_metrics)
            elif device.device_type == DeviceType.SWITCH:
                switching_metrics = await self._collect_snmp_switching_metrics(device)
                metrics.extend(switching_metrics)
            
        except Exception as e:
            self.logger.error(f"SNMP collection failed for {device.device_id}: {e}")
        finally:
            await self.snmp_client.disconnect()
        
        return metrics
    
    async def _collect_snmp_system_metrics(self, device: Device) -> List[Metric]:
        """Collect SNMP system metrics."""
        metrics = []
        timestamp = datetime.utcnow()
        
        # System uptime
        uptime = await self.snmp_client.get('1.3.6.1.2.1.1.3.0')
        if uptime:
            metrics.append(Metric(
                device_id=device.device_id,
                metric_type=MetricType.SYSTEM,
                name='system_uptime',
                value=float(uptime),
                unit='centiseconds',
                timestamp=timestamp
            ))
        
        # CPU utilization (if available)
        cpu_usage = await self.snmp_client.get('1.3.6.1.4.1.9.9.109.1.1.1.1.7.1')  # Cisco CPU
        if cpu_usage:
            metrics.append(Metric(
                device_id=device.device_id,
                metric_type=MetricType.PERFORMANCE,
                name='cpu_usage',
                value=float(cpu_usage),
                unit='percent',
                timestamp=timestamp
            ))
        
        # Memory utilization (if available)
        memory_used = await self.snmp_client.get('1.3.6.1.4.1.9.9.48.1.1.1.5.1')  # Cisco Memory Used
        memory_free = await self.snmp_client.get('1.3.6.1.4.1.9.9.48.1.1.1.6.1')  # Cisco Memory Free
        if memory_used and memory_free:
            total_memory = float(memory_used) + float(memory_free)
            memory_percent = (float(memory_used) / total_memory) * 100
            metrics.append(Metric(
                device_id=device.device_id,
                metric_type=MetricType.PERFORMANCE,
                name='memory_usage',
                value=memory_percent,
                unit='percent',
                timestamp=timestamp
            ))
        
        return metrics
    
    async def _collect_snmp_interface_metrics(self, device: Device) -> List[Metric]:
        """Collect SNMP interface metrics."""
        metrics = []
        timestamp = datetime.utcnow()
        
        # Get interface table
        interfaces = await self.snmp_client.walk('1.3.6.1.2.1.2.2.1.2')  # ifDescr
        
        for index, interface_name in interfaces.items():
            if_index = index.split('.')[-1]
            
            # Interface status
            admin_status = await self.snmp_client.get(f'1.3.6.1.2.1.2.2.1.7.{if_index}')
            oper_status = await self.snmp_client.get(f'1.3.6.1.2.1.2.2.1.8.{if_index}')
            
            # Interface counters
            in_octets = await self.snmp_client.get(f'1.3.6.1.2.1.2.2.1.10.{if_index}')
            out_octets = await self.snmp_client.get(f'1.3.6.1.2.1.2.2.1.16.{if_index}')
            in_errors = await self.snmp_client.get(f'1.3.6.1.2.1.2.2.1.14.{if_index}')
            out_errors = await self.snmp_client.get(f'1.3.6.1.2.1.2.2.1.20.{if_index}')
            
            # Interface speed
            if_speed = await self.snmp_client.get(f'1.3.6.1.2.1.2.2.1.5.{if_index}')
            
            # Create metrics
            if admin_status:
                metrics.append(Metric(
                    device_id=device.device_id,
                    metric_type=MetricType.NETWORK,
                    name=f'interface_{interface_name}_admin_status',
                    value=float(admin_status),
                    unit='status',
                    timestamp=timestamp,
                    tags={'interface': interface_name, 'index': if_index}
                ))
            
            if oper_status:
                metrics.append(Metric(
                    device_id=device.device_id,
                    metric_type=MetricType.NETWORK,
                    name=f'interface_{interface_name}_oper_status',
                    value=float(oper_status),
                    unit='status',
                    timestamp=timestamp,
                    tags={'interface': interface_name, 'index': if_index}
                ))
            
            if in_octets:
                metrics.append(Metric(
                    device_id=device.device_id,
                    metric_type=MetricType.NETWORK,
                    name=f'interface_{interface_name}_in_octets',
                    value=float(in_octets),
                    unit='bytes',
                    timestamp=timestamp,
                    tags={'interface': interface_name, 'index': if_index}
                ))
            
            if out_octets:
                metrics.append(Metric(
                    device_id=device.device_id,
                    metric_type=MetricType.NETWORK,
                    name=f'interface_{interface_name}_out_octets',
                    value=float(out_octets),
                    unit='bytes',
                    timestamp=timestamp,
                    tags={'interface': interface_name, 'index': if_index}
                ))
        
        return metrics
    
    async def _collect_snmp_routing_metrics(self, device: Device) -> List[Metric]:
        """Collect SNMP routing-specific metrics."""
        metrics = []
        timestamp = datetime.utcnow()
        
        # Routing table size
        routing_table = await self.snmp_client.walk('1.3.6.1.2.1.4.21.1.1')  # ipRouteDest
        if routing_table:
            metrics.append(Metric(
                device_id=device.device_id,
                metric_type=MetricType.NETWORK,
                name='routing_table_size',
                value=float(len(routing_table)),
                unit='routes',
                timestamp=timestamp
            ))
        
        return metrics
    
    async def _collect_snmp_switching_metrics(self, device: Device) -> List[Metric]:
        """Collect SNMP switching-specific metrics."""
        metrics = []
        timestamp = datetime.utcnow()
        
        # MAC address table size
        mac_table = await self.snmp_client.walk('1.3.6.1.2.1.17.4.3.1.1')  # dot1dTpFdbAddress
        if mac_table:
            metrics.append(Metric(
                device_id=device.device_id,
                metric_type=MetricType.NETWORK,
                name='mac_table_size',
                value=float(len(mac_table)),
                unit='entries',
                timestamp=timestamp
            ))
        
        return metrics
    
    async def collect_ssh_metrics(self, device: Device) -> List[Metric]:
        """
        Collect metrics via SSH.
        
        Args:
            device: Device to collect from
            
        Returns:
            List[Metric]: Collected metrics
        """
        metrics = []
        
        try:
            if not device.ssh_config:
                return metrics
            
            # Connect via SSH
            await self.ssh_client.connect(
                host=device.ip_address,
                username=device.ssh_config.get('username'),
                password=device.ssh_config.get('password'),
                private_key=device.ssh_config.get('private_key'),
                port=device.ssh_config.get('port', 22)
            )
            
            # Collect system metrics
            system_metrics = await self._collect_ssh_system_metrics(device)
            metrics.extend(system_metrics)
            
            # Collect network metrics
            network_metrics = await self._collect_ssh_network_metrics(device)
            metrics.extend(network_metrics)
            
        except Exception as e:
            self.logger.error(f"SSH collection failed for {device.device_id}: {e}")
        finally:
            await self.ssh_client.disconnect()
        
        return metrics
    
    async def _collect_ssh_system_metrics(self, device: Device) -> List[Metric]:
        """Collect system metrics via SSH."""
        metrics = []
        timestamp = datetime.utcnow()
        
        # CPU usage
        cpu_output = await self.ssh_client.execute_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
        if cpu_output and cpu_output.strip():
            try:
                cpu_usage = float(cpu_output.strip())
                metrics.append(Metric(
                    device_id=device.device_id,
                    metric_type=MetricType.PERFORMANCE,
                    name='cpu_usage',
                    value=cpu_usage,
                    unit='percent',
                    timestamp=timestamp
                ))
            except ValueError:
                pass
        
        # Memory usage
        mem_output = await self.ssh_client.execute_command("free | grep Mem | awk '{printf \"%.2f\", $3/$2 * 100.0}'")
        if mem_output and mem_output.strip():
            try:
                memory_usage = float(mem_output.strip())
                metrics.append(Metric(
                    device_id=device.device_id,
                    metric_type=MetricType.PERFORMANCE,
                    name='memory_usage',
                    value=memory_usage,
                    unit='percent',
                    timestamp=timestamp
                ))
            except ValueError:
                pass
        
        # Disk usage
        disk_output = await self.ssh_client.execute_command("df -h / | awk 'NR==2 {print $5}' | cut -d'%' -f1")
        if disk_output and disk_output.strip():
            try:
                disk_usage = float(disk_output.strip())
                metrics.append(Metric(
                    device_id=device.device_id,
                    metric_type=MetricType.PERFORMANCE,
                    name='disk_usage',
                    value=disk_usage,
                    unit='percent',
                    timestamp=timestamp
                ))
            except ValueError:
                pass
        
        # Load average
        load_output = await self.ssh_client.execute_command("uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | cut -d',' -f1")
        if load_output and load_output.strip():
            try:
                load_avg = float(load_output.strip())
                metrics.append(Metric(
                    device_id=device.device_id,
                    metric_type=MetricType.PERFORMANCE,
                    name='load_average_1m',
                    value=load_avg,
                    unit='load',
                    timestamp=timestamp
                ))
            except ValueError:
                pass
        
        return metrics
    
    async def _collect_ssh_network_metrics(self, device: Device) -> List[Metric]:
        """Collect network metrics via SSH."""
        metrics = []
        timestamp = datetime.utcnow()
        
        # Network interface statistics
        netstat_output = await self.ssh_client.execute_command("cat /proc/net/dev | tail -n +3")
        if netstat_output:
            for line in netstat_output.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 17:
                    interface = parts[0].rstrip(':')
                    rx_bytes = int(parts[1])
                    tx_bytes = int(parts[9])
                    
                    metrics.append(Metric(
                        device_id=device.device_id,
                        metric_type=MetricType.NETWORK,
                        name=f'interface_{interface}_rx_bytes',
                        value=float(rx_bytes),
                        unit='bytes',
                        timestamp=timestamp,
                        tags={'interface': interface}
                    ))
                    
                    metrics.append(Metric(
                        device_id=device.device_id,
                        metric_type=MetricType.NETWORK,
                        name=f'interface_{interface}_tx_bytes',
                        value=float(tx_bytes),
                        unit='bytes',
                        timestamp=timestamp,
                        tags={'interface': interface}
                    ))
        
        return metrics
    
    async def collect_web_metrics(self, device: Device) -> List[Metric]:
        """
        Collect metrics from web interface.
        
        Args:
            device: Device to collect from
            
        Returns:
            List[Metric]: Collected metrics
        """
        metrics = []
        
        try:
            if not device.web_config:
                return metrics
            
            # Configure web scraper
            self.web_scraper.configure(
                base_url=device.web_config.get('base_url'),
                username=device.web_config.get('username'),
                password=device.web_config.get('password'),
                timeout=self.config.timeout
            )
            
            # Scrape metrics based on device type
            if device.device_type == DeviceType.ACCESS_POINT:
                metrics = await self._collect_web_ap_metrics(device)
            elif device.device_type == DeviceType.FIREWALL:
                metrics = await self._collect_web_firewall_metrics(device)
            
        except Exception as e:
            self.logger.error(f"Web collection failed for {device.device_id}: {e}")
        
        return metrics
    
    async def _collect_web_ap_metrics(self, device: Device) -> List[Metric]:
        """Collect access point metrics from web interface."""
        metrics = []
        timestamp = datetime.utcnow()
        
        # This would be device-specific implementation
        # Example for Ubiquiti UniFi AP
        status_data = await self.web_scraper.get_json('/api/s/default/stat/device')
        
        if status_data and 'data' in status_data:
            for ap_data in status_data['data']:
                if ap_data.get('mac') == device.mac_address:
                    # Client count
                    if 'num_sta' in ap_data:
                        metrics.append(Metric(
                            device_id=device.device_id,
                            metric_type=MetricType.NETWORK,
                            name='connected_clients',
                            value=float(ap_data['num_sta']),
                            unit='clients',
                            timestamp=timestamp
                        ))
                    
                    # Signal strength
                    if 'satisfaction' in ap_data:
                        metrics.append(Metric(
                            device_id=device.device_id,
                            metric_type=MetricType.NETWORK,
                            name='satisfaction',
                            value=float(ap_data['satisfaction']),
                            unit='percent',
                            timestamp=timestamp
                        ))
        
        return metrics
    
    async def _collect_web_firewall_metrics(self, device: Device) -> List[Metric]:
        """Collect firewall metrics from web interface."""
        metrics = []
        timestamp = datetime.utcnow()
        
        # This would be device-specific implementation
        # Example for pfSense
        status_data = await self.web_scraper.get_json('/api/v1/status/system')
        
        if status_data:
            # CPU usage
            if 'cpu_usage' in status_data:
                metrics.append(Metric(
                    device_id=device.device_id,
                    metric_type=MetricType.PERFORMANCE,
                    name='cpu_usage',
                    value=float(status_data['cpu_usage']),
                    unit='percent',
                    timestamp=timestamp
                ))
            
            # Memory usage
            if 'memory_usage' in status_data:
                metrics.append(Metric(
                    device_id=device.device_id,
                    metric_type=MetricType.PERFORMANCE,
                    name='memory_usage',
                    value=float(status_data['memory_usage']),
                    unit='percent',
                    timestamp=timestamp
                ))
        
        return metrics
    
    async def collect_api_metrics(self, device: Device) -> List[Metric]:
        """
        Collect metrics from REST API.
        
        Args:
            device: Device to collect from
            
        Returns:
            List[Metric]: Collected metrics
        """
        metrics = []
        
        try:
            if not device.api_config:
                return metrics
            
            # Configure REST client
            self.rest_client.configure(
                base_url=device.api_config.get('base_url'),
                auth_token=device.api_config.get('auth_token'),
                api_key=device.api_config.get('api_key'),
                timeout=self.config.timeout
            )
            
            # Collect metrics from API endpoints
            endpoints = device.api_config.get('endpoints', [])
            for endpoint in endpoints:
                endpoint_metrics = await self._collect_api_endpoint_metrics(device, endpoint)
                metrics.extend(endpoint_metrics)
            
        except Exception as e:
            self.logger.error(f"API collection failed for {device.device_id}: {e}")
        
        return metrics
    
    async def _collect_api_endpoint_metrics(self, device: Device, endpoint: Dict[str, Any]) -> List[Metric]:
        """Collect metrics from a specific API endpoint."""
        metrics = []
        timestamp = datetime.utcnow()
        
        try:
            url = endpoint.get('url')
            metric_mappings = endpoint.get('metrics', {})
            
            data = await self.rest_client.get(url)
            
            for metric_name, json_path in metric_mappings.items():
                value = self._extract_json_value(data, json_path)
                if value is not None:
                    metrics.append(Metric(
                        device_id=device.device_id,
                        metric_type=MetricType.CUSTOM,
                        name=metric_name,
                        value=float(value),
                        unit=endpoint.get('unit', 'value'),
                        timestamp=timestamp
                    ))
        
        except Exception as e:
            self.logger.error(f"API endpoint collection failed: {e}")
        
        return metrics
    
    def _extract_json_value(self, data: Dict[str, Any], json_path: str) -> Any:
        """Extract value from JSON data using dot notation path."""
        try:
            keys = json_path.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and key.isdigit():
                    value = value[int(key)]
                else:
                    return None
            return value
        except (KeyError, IndexError, TypeError):
            return None
    
    async def collect_system_metrics(self) -> List[Metric]:
        """
        Collect local system metrics.
        
        Returns:
            List[Metric]: System metrics
        """
        metrics = []
        timestamp = datetime.utcnow()
        
        try:
            # Get system metrics from platform
            system_metrics = self.platform.get_system_metrics()
            
            # Convert to Metric objects
            metrics.extend([
                Metric(
                    device_id='localhost',
                    metric_type=MetricType.PERFORMANCE,
                    name='cpu_usage',
                    value=system_metrics.cpu_percent,
                    unit='percent',
                    timestamp=timestamp
                ),
                Metric(
                    device_id='localhost',
                    metric_type=MetricType.PERFORMANCE,
                    name='memory_usage',
                    value=system_metrics.memory_percent,
                    unit='percent',
                    timestamp=timestamp
                ),
                Metric(
                    device_id='localhost',
                    metric_type=MetricType.PERFORMANCE,
                    name='disk_usage',
                    value=system_metrics.disk_percent,
                    unit='percent',
                    timestamp=timestamp
                )
            ])
            
            # Add load average if available
            if system_metrics.load_average:
                metrics.append(Metric(
                    device_id='localhost',
                    metric_type=MetricType.PERFORMANCE,
                    name='load_average_1m',
                    value=system_metrics.load_average[0],
                    unit='load',
                    timestamp=timestamp
                ))
            
            # Get network interfaces
            interfaces = self.platform.get_network_interfaces()
            for interface in interfaces:
                if interface.rx_bytes is not None:
                    metrics.append(Metric(
                        device_id='localhost',
                        metric_type=MetricType.NETWORK,
                        name=f'interface_{interface.name}_rx_bytes',
                        value=float(interface.rx_bytes),
                        unit='bytes',
                        timestamp=timestamp,
                        tags={'interface': interface.name}
                    ))
                
                if interface.tx_bytes is not None:
                    metrics.append(Metric(
                        device_id='localhost',
                        metric_type=MetricType.NETWORK,
                        name=f'interface_{interface.name}_tx_bytes',
                        value=float(interface.tx_bytes),
                        unit='bytes',
                        timestamp=timestamp,
                        tags={'interface': interface.name}
                    ))
        
        except Exception as e:
            self.logger.error(f"System metrics collection failed: {e}")
        
        return metrics
    
    async def collect_device_metrics(self, device: Device) -> CollectionResult:
        """
        Collect all metrics for a single device.
        
        Args:
            device: Device to collect metrics from
            
        Returns:
            CollectionResult: Collection result
        """
        start_time = time.time()
        all_metrics = []
        status = CollectionStatus.SUCCESS
        error_message = None
        
        try:
            # Collect from enabled sources
            if 'snmp' in self.config.enabled_collectors and device.snmp_config:
                snmp_metrics = await self.collect_snmp_metrics(device)
                all_metrics.extend(snmp_metrics)
            
            if 'ssh' in self.config.enabled_collectors and device.ssh_config:
                ssh_metrics = await self.collect_ssh_metrics(device)
                all_metrics.extend(ssh_metrics)
            
            if 'web' in self.config.enabled_collectors and device.web_config:
                web_metrics = await self.collect_web_metrics(device)
                all_metrics.extend(web_metrics)
            
            if 'api' in self.config.enabled_collectors and device.api_config:
                api_metrics = await self.collect_api_metrics(device)
                all_metrics.extend(api_metrics)
            
            # Update cache
            self.metrics_cache[device.device_id] = all_metrics
            
        except asyncio.TimeoutError:
            status = CollectionStatus.TIMEOUT
            error_message = "Collection timeout"
        except ConnectionError:
            status = CollectionStatus.UNREACHABLE
            error_message = "Device unreachable"
        except PermissionError:
            status = CollectionStatus.UNAUTHORIZED
            error_message = "Authentication failed"
        except Exception as e:
            status = CollectionStatus.FAILED
            error_message = str(e)
        
        duration = time.time() - start_time
        
        result = CollectionResult(
            device_id=device.device_id,
            metrics=all_metrics,
            status=status,
            timestamp=datetime.utcnow(),
            duration=duration,
            error_message=error_message
        )
        
        # Store in history
        self.collection_history.append(result)
        
        # Keep only recent history
        if len(self.collection_history) > 1000:
            self.collection_history = self.collection_history[-1000:]
        
        # Call callbacks
        for callback in self.collection_callbacks:
            try:
                callback(result)
            except Exception as e:
                self.logger.error(f"Collection callback failed: {e}")
        
        return result
    
    async def collect_all_metrics(self) -> List[CollectionResult]:
        """
        Collect metrics from all devices.
        
        Returns:
            List[CollectionResult]: Collection results for all devices
        """
        results = []
        
        # Collect system metrics if enabled
        if 'system' in self.config.enabled_collectors:
            try:
                system_metrics = await self.collect_system_metrics()
                system_result = CollectionResult(
                    device_id='localhost',
                    metrics=system_metrics,
                    status=CollectionStatus.SUCCESS,
                    timestamp=datetime.utcnow(),
                    duration=0.1
                )
                results.append(system_result)
            except Exception as e:
                self.logger.error(f"System metrics collection failed: {e}")
        
        # Collect device metrics in batches
        devices = list(self.devices.values())
        for i in range(0, len(devices), self.config.batch_size):
            batch = devices[i:i + self.config.batch_size]
            
            # Collect batch concurrently
            tasks = [self.collect_device_metrics(device) for device in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, CollectionResult):
                    results.append(result)
                else:
                    self.logger.error(f"Collection task failed: {result}")
        
        return results
    
    async def start_collection(self):
        """Start periodic metric collection."""
        if self.is_running:
            return
        
        self.is_running = True
        self.collection_task = asyncio.create_task(self._collection_loop())
        self.logger.info("Metric collection started")
    
    async def stop_collection(self):
        """Stop periodic metric collection."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Metric collection stopped")
    
    async def _collection_loop(self):
        """Main collection loop."""
        while self.is_running:
            try:
                self.logger.debug("Starting metric collection cycle")
                results = await self.collect_all_metrics()
                
                success_count = len([r for r in results if r.status == CollectionStatus.SUCCESS])
                total_metrics = sum(len(r.metrics) for r in results)
                
                self.logger.info(f"Collection cycle completed: {success_count}/{len(results)} devices, {total_metrics} metrics")
                
                # Wait for next collection
                await asyncio.sleep(self.config.interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Collection loop error: {e}")
                await asyncio.sleep(self.config.interval)
    
    def get_cached_metrics(self, device_id: str, max_age: int = None) -> Optional[List[Metric]]:
        """
        Get cached metrics for a device.
        
        Args:
            device_id: Device ID
            max_age: Maximum age in seconds (uses cache_ttl if None)
            
        Returns:
            List[Metric]: Cached metrics or None if not available/expired
        """
        if device_id not in self.metrics_cache:
            return None
        
        metrics = self.metrics_cache[device_id]
        if not metrics:
            return None
        
        # Check age
        max_age = max_age or self.cache_ttl
        latest_metric = max(metrics, key=lambda m: m.timestamp)
        age = (datetime.utcnow() - latest_metric.timestamp).total_seconds()
        
        if age > max_age:
            return None
        
        return metrics
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        if not self.collection_history:
            return {}
        
        recent_results = [
            r for r in self.collection_history
            if (datetime.utcnow() - r.timestamp).total_seconds() < 3600  # Last hour
        ]
        
        if not recent_results:
            return {}
        
        success_count = len([r for r in recent_results if r.status == CollectionStatus.SUCCESS])
        total_metrics = sum(len(r.metrics) for r in recent_results)
        avg_duration = sum(r.duration for r in recent_results) / len(recent_results)
        
        status_counts = {}
        for status in CollectionStatus:
            status_counts[status.value] = len([r for r in recent_results if r.status == status])
        
        return {
            'total_collections': len(recent_results),
            'success_rate': success_count / len(recent_results) * 100,
            'total_metrics': total_metrics,
            'avg_duration': avg_duration,
            'status_counts': status_counts,
            'devices_monitored': len(self.devices),
            'is_running': self.is_running
        }