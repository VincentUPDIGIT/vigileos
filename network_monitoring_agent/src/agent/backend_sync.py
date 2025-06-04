"""
Backend synchronization for metrics and device data.
"""

import asyncio
import logging
import json
import gzip
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import time

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from models.metric import Metric, MetricCollection
from models.device import Device
from models.client import Client
from utils.encryption import EncryptionManager
from utils.platform_utils import PlatformPaths


class SyncStatus(Enum):
    """Synchronization status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    PENDING = "pending"
    RETRYING = "retrying"


@dataclass
class SyncResult:
    """Synchronization result."""
    status: SyncStatus
    timestamp: datetime
    metrics_sent: int = 0
    devices_sent: int = 0
    bytes_sent: int = 0
    duration: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class BackendConfig:
    """Backend configuration."""
    base_url: str
    auth_token: Optional[str] = None
    api_key: Optional[str] = None
    client_id: Optional[str] = None
    timeout: int = 30
    verify_ssl: bool = True
    compression: bool = True
    batch_size: int = 100
    retry_attempts: int = 3
    retry_delay: int = 5
    sync_interval: int = 60


class BackendError(Exception):
    """Backend synchronization error."""
    pass


class BackendSync:
    """
    Backend synchronization manager.
    
    Handles uploading metrics, device inventory, and receiving
    commands from the backend monitoring system.
    """
    
    def __init__(self, config: BackendConfig):
        """
        Initialize backend sync.
        
        Args:
            config: Backend configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.encryption_manager = EncryptionManager()
        
        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Sync state
        self.is_running = False
        self.sync_task = None
        self.last_sync: Optional[datetime] = None
        self.sync_history: List[SyncResult] = []
        
        # Queues for data to sync
        self.metrics_queue: List[Metric] = []
        self.devices_queue: List[Device] = []
        self.pending_commands: List[Dict[str, Any]] = []
        
        # Callbacks
        self.command_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Offline storage
        self.offline_storage_path = PlatformPaths.get_data_dir() / "offline_sync"
        self.offline_storage_path.mkdir(parents=True, exist_ok=True)
        
        if not AIOHTTP_AVAILABLE:
            self.logger.warning("aiohttp not available, backend sync disabled")
        
        self.logger.info(f"BackendSync initialized for {config.base_url}")
    
    async def start_session(self):
        """Start HTTP session."""
        if not AIOHTTP_AVAILABLE:
            raise BackendError("aiohttp not available")
        
        if self.session and not self.session.closed:
            return
        
        # Setup headers
        headers = {
            'User-Agent': 'NetworkMonitoringAgent/1.0',
            'Content-Type': 'application/json'
        }
        
        if self.config.auth_token:
            headers['Authorization'] = f'Bearer {self.config.auth_token}'
        elif self.config.api_key:
            headers['X-API-Key'] = self.config.api_key
        
        # Setup SSL context
        ssl_context = None if self.config.verify_ssl else False
        
        # Create session
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            connector=aiohttp.TCPConnector(ssl=ssl_context)
        )
        
        self.logger.debug("Backend HTTP session started")
    
    async def close_session(self):
        """Close HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
        self.logger.debug("Backend HTTP session closed")
    
    async def test_connection(self) -> bool:
        """
        Test backend connection.
        
        Returns:
            bool: True if connection is working
        """
        try:
            await self.start_session()
            
            async with self.session.get(f"{self.config.base_url}/health") as response:
                return response.status == 200
                
        except Exception as e:
            self.logger.debug(f"Backend connection test failed: {e}")
            return False
    
    def add_metrics(self, metrics: List[Metric]):
        """Add metrics to sync queue."""
        self.metrics_queue.extend(metrics)
        self.logger.debug(f"Added {len(metrics)} metrics to sync queue")
    
    def add_devices(self, devices: List[Device]):
        """Add devices to sync queue."""
        self.devices_queue.extend(devices)
        self.logger.debug(f"Added {len(devices)} devices to sync queue")
    
    def add_command_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for backend commands."""
        self.command_callbacks.append(callback)
    
    async def push_metrics_batch(self, metrics: List[Metric]) -> SyncResult:
        """
        Push batch of metrics to backend.
        
        Args:
            metrics: List of metrics to send
            
        Returns:
            SyncResult: Synchronization result
        """
        start_time = time.time()
        result = SyncResult(
            status=SyncStatus.PENDING,
            timestamp=datetime.utcnow()
        )
        
        try:
            await self.start_session()
            
            # Convert metrics to dict format
            metrics_data = [metric.to_dict() for metric in metrics]
            
            # Prepare payload
            payload = {
                'client_id': self.config.client_id,
                'timestamp': datetime.utcnow().isoformat(),
                'metrics': metrics_data,
                'count': len(metrics_data)
            }
            
            # Compress if enabled
            if self.config.compression:
                json_data = json.dumps(payload)
                compressed_data = gzip.compress(json_data.encode('utf-8'))
                
                headers = {'Content-Encoding': 'gzip'}
                data = compressed_data
            else:
                headers = {}
                data = json.dumps(payload).encode('utf-8')
            
            # Send to backend
            async with self.session.post(
                f"{self.config.base_url}/api/v1/metrics",
                data=data,
                headers=headers
            ) as response:
                
                if response.status == 200:
                    result.status = SyncStatus.SUCCESS
                    result.metrics_sent = len(metrics)
                    result.bytes_sent = len(data)
                else:
                    error_text = await response.text()
                    result.status = SyncStatus.FAILED
                    result.error_message = f"HTTP {response.status}: {error_text}"
            
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.error_message = str(e)
            self.logger.error(f"Metrics sync failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    async def sync_device_inventory(self, devices: List[Device]) -> SyncResult:
        """
        Sync device inventory with backend.
        
        Args:
            devices: List of devices to sync
            
        Returns:
            SyncResult: Synchronization result
        """
        start_time = time.time()
        result = SyncResult(
            status=SyncStatus.PENDING,
            timestamp=datetime.utcnow()
        )
        
        try:
            await self.start_session()
            
            # Convert devices to dict format
            devices_data = [device.to_dict() for device in devices]
            
            # Prepare payload
            payload = {
                'client_id': self.config.client_id,
                'timestamp': datetime.utcnow().isoformat(),
                'devices': devices_data,
                'count': len(devices_data)
            }
            
            # Send to backend
            async with self.session.post(
                f"{self.config.base_url}/api/v1/devices",
                json=payload
            ) as response:
                
                if response.status == 200:
                    result.status = SyncStatus.SUCCESS
                    result.devices_sent = len(devices)
                else:
                    error_text = await response.text()
                    result.status = SyncStatus.FAILED
                    result.error_message = f"HTTP {response.status}: {error_text}"
        
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.error_message = str(e)
            self.logger.error(f"Device sync failed: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    async def handle_backend_commands(self) -> List[Dict[str, Any]]:
        """
        Fetch and handle commands from backend.
        
        Returns:
            List[Dict[str, Any]]: List of commands received
        """
        try:
            await self.start_session()
            
            # Fetch commands
            params = {'client_id': self.config.client_id}
            async with self.session.get(
                f"{self.config.base_url}/api/v1/commands",
                params=params
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    commands = data.get('commands', [])
                    
                    # Process commands
                    for command in commands:
                        await self._process_command(command)
                    
                    return commands
                else:
                    self.logger.warning(f"Failed to fetch commands: HTTP {response.status}")
                    return []
        
        except Exception as e:
            self.logger.error(f"Command handling failed: {e}")
            return []
    
    async def _process_command(self, command: Dict[str, Any]):
        """Process a single command from backend."""
        try:
            command_type = command.get('type')
            command_id = command.get('id')
            
            self.logger.info(f"Processing command {command_id}: {command_type}")
            
            # Call registered callbacks
            for callback in self.command_callbacks:
                try:
                    callback(command)
                except Exception as e:
                    self.logger.error(f"Command callback failed: {e}")
            
            # Acknowledge command
            await self._acknowledge_command(command_id)
            
        except Exception as e:
            self.logger.error(f"Command processing failed: {e}")
    
    async def _acknowledge_command(self, command_id: str):
        """Acknowledge command completion."""
        try:
            payload = {
                'client_id': self.config.client_id,
                'command_id': command_id,
                'status': 'completed',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            async with self.session.post(
                f"{self.config.base_url}/api/v1/commands/ack",
                json=payload
            ) as response:
                
                if response.status != 200:
                    self.logger.warning(f"Failed to acknowledge command {command_id}")
        
        except Exception as e:
            self.logger.error(f"Command acknowledgment failed: {e}")
    
    async def retry_failed_uploads(self) -> int:
        """
        Retry failed uploads from offline storage.
        
        Returns:
            int: Number of successful retries
        """
        retry_count = 0
        
        try:
            # Load offline data
            offline_files = list(self.offline_storage_path.glob("*.json"))
            
            for file_path in offline_files:
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    
                    # Retry upload
                    if data.get('type') == 'metrics':
                        metrics = [Metric.from_dict(m) for m in data['data']]
                        result = await self.push_metrics_batch(metrics)
                    elif data.get('type') == 'devices':
                        devices = [Device.from_dict(d) for d in data['data']]
                        result = await self.sync_device_inventory(devices)
                    else:
                        continue
                    
                    # Remove file if successful
                    if result.status == SyncStatus.SUCCESS:
                        file_path.unlink()
                        retry_count += 1
                        self.logger.info(f"Retry successful for {file_path.name}")
                
                except Exception as e:
                    self.logger.error(f"Retry failed for {file_path.name}: {e}")
        
        except Exception as e:
            self.logger.error(f"Retry process failed: {e}")
        
        return retry_count
    
    def _save_offline_data(self, data_type: str, data: List[Dict[str, Any]]):
        """Save data for offline retry."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{data_type}_{timestamp}.json"
            file_path = self.offline_storage_path / filename
            
            offline_data = {
                'type': data_type,
                'timestamp': datetime.utcnow().isoformat(),
                'data': data
            }
            
            with open(file_path, 'w') as f:
                json.dump(offline_data, f, indent=2)
            
            self.logger.info(f"Saved {len(data)} {data_type} items for offline retry")
        
        except Exception as e:
            self.logger.error(f"Failed to save offline data: {e}")
    
    async def sync_all_queued_data(self) -> SyncResult:
        """
        Sync all queued data.
        
        Returns:
            SyncResult: Overall synchronization result
        """
        start_time = time.time()
        overall_result = SyncResult(
            status=SyncStatus.SUCCESS,
            timestamp=datetime.utcnow()
        )
        
        try:
            # Sync metrics in batches
            if self.metrics_queue:
                metrics_to_sync = self.metrics_queue.copy()
                self.metrics_queue.clear()
                
                for i in range(0, len(metrics_to_sync), self.config.batch_size):
                    batch = metrics_to_sync[i:i + self.config.batch_size]
                    result = await self.push_metrics_batch(batch)
                    
                    if result.status == SyncStatus.SUCCESS:
                        overall_result.metrics_sent += result.metrics_sent
                        overall_result.bytes_sent += result.bytes_sent
                    else:
                        # Save failed batch for retry
                        batch_data = [m.to_dict() for m in batch]
                        self._save_offline_data('metrics', batch_data)
                        overall_result.status = SyncStatus.PARTIAL
            
            # Sync devices
            if self.devices_queue:
                devices_to_sync = self.devices_queue.copy()
                self.devices_queue.clear()
                
                result = await self.sync_device_inventory(devices_to_sync)
                
                if result.status == SyncStatus.SUCCESS:
                    overall_result.devices_sent += result.devices_sent
                else:
                    # Save failed devices for retry
                    devices_data = [d.to_dict() for d in devices_to_sync]
                    self._save_offline_data('devices', devices_data)
                    overall_result.status = SyncStatus.PARTIAL
            
            # Handle backend commands
            commands = await self.handle_backend_commands()
            if commands:
                self.logger.info(f"Processed {len(commands)} backend commands")
        
        except Exception as e:
            overall_result.status = SyncStatus.FAILED
            overall_result.error_message = str(e)
            self.logger.error(f"Sync failed: {e}")
        
        overall_result.duration = time.time() - start_time
        
        # Store sync result
        self.sync_history.append(overall_result)
        self.last_sync = overall_result.timestamp
        
        # Keep only recent history
        if len(self.sync_history) > 100:
            self.sync_history = self.sync_history[-100:]
        
        return overall_result
    
    async def start_periodic_sync(self):
        """Start periodic synchronization."""
        if self.is_running:
            return
        
        self.is_running = True
        self.sync_task = asyncio.create_task(self._sync_loop())
        self.logger.info("Periodic sync started")
    
    async def stop_periodic_sync(self):
        """Stop periodic synchronization."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Periodic sync stopped")
    
    async def _sync_loop(self):
        """Main synchronization loop."""
        while self.is_running:
            try:
                # Perform sync
                result = await self.sync_all_queued_data()
                
                # Log result
                if result.status == SyncStatus.SUCCESS:
                    self.logger.info(
                        f"Sync completed: {result.metrics_sent} metrics, "
                        f"{result.devices_sent} devices in {result.duration:.2f}s"
                    )
                else:
                    self.logger.warning(f"Sync {result.status.value}: {result.error_message}")
                
                # Retry failed uploads
                retry_count = await self.retry_failed_uploads()
                if retry_count > 0:
                    self.logger.info(f"Retried {retry_count} failed uploads")
                
                # Wait for next sync
                await asyncio.sleep(self.config.sync_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Sync loop error: {e}")
                await asyncio.sleep(self.config.sync_interval)
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics."""
        if not self.sync_history:
            return {}
        
        recent_syncs = [s for s in self.sync_history 
                       if (datetime.utcnow() - s.timestamp).total_seconds() < 3600]
        
        if not recent_syncs:
            return {}
        
        success_count = len([s for s in recent_syncs if s.status == SyncStatus.SUCCESS])
        total_metrics = sum(s.metrics_sent for s in recent_syncs)
        total_devices = sum(s.devices_sent for s in recent_syncs)
        avg_duration = sum(s.duration for s in recent_syncs) / len(recent_syncs)
        
        return {
            'total_syncs': len(recent_syncs),
            'success_rate': success_count / len(recent_syncs) * 100,
            'total_metrics_sent': total_metrics,
            'total_devices_sent': total_devices,
            'avg_duration': avg_duration,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'queue_sizes': {
                'metrics': len(self.metrics_queue),
                'devices': len(self.devices_queue)
            },
            'is_running': self.is_running
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()