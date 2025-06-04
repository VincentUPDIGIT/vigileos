"""
Cross-platform tunnel manager for secure remote access.
"""

import asyncio
import logging
import subprocess
import json
import secrets
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

from platforms.platform_factory import PlatformFactory
from platforms.base_platform import TunnelConfig, TunnelType
from utils.platform_utils import PlatformPaths, PlatformUtils
from utils.encryption import EncryptionManager


class TunnelStatus(Enum):
    """Tunnel status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CONNECTING = "connecting"
    DISCONNECTING = "disconnecting"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class TunnelInfo:
    """Tunnel information data structure."""
    tunnel_id: str
    name: str
    tunnel_type: TunnelType
    status: TunnelStatus
    local_endpoint: str
    remote_endpoint: str
    created_at: datetime
    last_connected: Optional[datetime] = None
    bytes_sent: int = 0
    bytes_received: int = 0
    client_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['tunnel_type'] = self.tunnel_type.value
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['last_connected'] = self.last_connected.isoformat() if self.last_connected else None
        return data


class TunnelError(Exception):
    """Tunnel-related error."""
    pass


class TunnelManager:
    """
    Cross-platform tunnel manager.
    
    Manages WireGuard, SSH, and OpenVPN tunnels for secure remote access
    to monitored networks and devices.
    """
    
    def __init__(self):
        """Initialize tunnel manager."""
        self.logger = logging.getLogger(__name__)
        self.platform = PlatformFactory.get_platform()
        self.encryption_manager = EncryptionManager()
        
        # Tunnel storage
        self.active_tunnels: Dict[str, TunnelInfo] = {}
        self.tunnel_configs: Dict[str, TunnelConfig] = {}
        
        # Configuration paths
        self.config_dir = PlatformPaths.get_config_dir() / "tunnels"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing tunnels
        self._load_tunnel_configs()
        
        self.logger.info(f"TunnelManager initialized on {self.platform.platform_name}")
    
    def _load_tunnel_configs(self):
        """Load tunnel configurations from storage."""
        try:
            config_file = self.config_dir / "tunnels.json"
            if config_file.exists():
                with open(config_file, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted_data = self.encryption_manager.decrypt(encrypted_data)
                configs_data = json.loads(decrypted_data)
                
                for tunnel_id, config_data in configs_data.items():
                    # Reconstruct TunnelConfig
                    tunnel_type = TunnelType(config_data.pop('tunnel_type'))
                    config = TunnelConfig(
                        tunnel_type=tunnel_type,
                        **config_data
                    )
                    self.tunnel_configs[tunnel_id] = config
                
                self.logger.info(f"Loaded {len(self.tunnel_configs)} tunnel configurations")
        
        except Exception as e:
            self.logger.warning(f"Failed to load tunnel configurations: {e}")
    
    def _save_tunnel_configs(self):
        """Save tunnel configurations to storage."""
        try:
            configs_data = {}
            for tunnel_id, config in self.tunnel_configs.items():
                config_dict = asdict(config)
                config_dict['tunnel_type'] = config.tunnel_type.value
                configs_data[tunnel_id] = config_dict
            
            json_data = json.dumps(configs_data, indent=2)
            encrypted_data = self.encryption_manager.encrypt(json_data.encode())
            
            config_file = self.config_dir / "tunnels.json"
            with open(config_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Set secure permissions
            config_file.chmod(0o600)
            
        except Exception as e:
            self.logger.error(f"Failed to save tunnel configurations: {e}")
    
    def generate_tunnel_id(self) -> str:
        """Generate unique tunnel ID."""
        return f"tunnel_{secrets.token_hex(8)}"
    
    async def create_wireguard_tunnel(self, name: str, remote_endpoint: str,
                                    public_key: str, allowed_ips: List[str],
                                    local_ip: str = None, private_key: str = None,
                                    client_id: str = None,
                                    additional_config: Dict[str, Any] = None) -> str:
        """
        Create WireGuard tunnel.
        
        Args:
            name: Tunnel name
            remote_endpoint: Remote endpoint (host:port)
            public_key: Remote public key
            allowed_ips: List of allowed IP ranges
            local_ip: Local IP address for tunnel
            private_key: Local private key (generated if None)
            client_id: Client ID for multi-tenant support
            additional_config: Additional configuration options
            
        Returns:
            str: Tunnel ID
            
        Raises:
            TunnelError: If tunnel creation fails
        """
        try:
            tunnel_id = self.generate_tunnel_id()
            
            # Generate keys if not provided
            if not private_key:
                private_key, public_key_local = self._generate_wireguard_keys()
            
            # Auto-assign local IP if not provided
            if not local_ip:
                local_ip = self._get_available_tunnel_ip()
            
            # Create tunnel configuration
            config = TunnelConfig(
                tunnel_type=TunnelType.WIREGUARD,
                name=name,
                local_ip=local_ip,
                remote_ip=remote_endpoint.split(':')[0],
                local_port=None,
                remote_port=int(remote_endpoint.split(':')[1]) if ':' in remote_endpoint else 51820,
                private_key=private_key,
                public_key=public_key,
                endpoint=remote_endpoint,
                allowed_ips=allowed_ips,
                config_data=additional_config or {}
            )
            
            # Create tunnel using platform-specific implementation
            success = await self.platform.create_tunnel_interface(config)
            
            if not success:
                raise TunnelError("Platform tunnel creation failed")
            
            # Store configuration
            self.tunnel_configs[tunnel_id] = config
            self._save_tunnel_configs()
            
            # Create tunnel info
            tunnel_info = TunnelInfo(
                tunnel_id=tunnel_id,
                name=name,
                tunnel_type=TunnelType.WIREGUARD,
                status=TunnelStatus.ACTIVE,
                local_endpoint=local_ip,
                remote_endpoint=remote_endpoint,
                created_at=datetime.utcnow(),
                last_connected=datetime.utcnow(),
                client_id=client_id,
                config=asdict(config)
            )
            
            self.active_tunnels[tunnel_id] = tunnel_info
            
            self.logger.info(f"WireGuard tunnel created: {tunnel_id} ({name})")
            return tunnel_id
            
        except Exception as e:
            self.logger.error(f"Failed to create WireGuard tunnel: {e}")
            raise TunnelError(f"WireGuard tunnel creation failed: {e}")
    
    async def create_ssh_tunnel(self, name: str, ssh_host: str, ssh_port: int,
                              local_port: int, remote_host: str, remote_port: int,
                              username: str, password: str = None, private_key: str = None,
                              client_id: str = None) -> str:
        """
        Create SSH tunnel.
        
        Args:
            name: Tunnel name
            ssh_host: SSH server host
            ssh_port: SSH server port
            local_port: Local port to bind
            remote_host: Remote host to connect to through tunnel
            remote_port: Remote port to connect to
            username: SSH username
            password: SSH password
            private_key: SSH private key
            client_id: Client ID for multi-tenant support
            
        Returns:
            str: Tunnel ID
            
        Raises:
            TunnelError: If tunnel creation fails
        """
        try:
            tunnel_id = self.generate_tunnel_id()
            
            # Create tunnel configuration
            config = TunnelConfig(
                tunnel_type=TunnelType.SSH,
                name=name,
                local_ip="127.0.0.1",
                remote_ip=remote_host,
                local_port=local_port,
                remote_port=remote_port,
                endpoint=f"{ssh_host}:{ssh_port}",
                config_data={
                    'ssh_host': ssh_host,
                    'ssh_port': ssh_port,
                    'username': username,
                    'password': password,
                    'private_key': private_key
                }
            )
            
            # Create tunnel using platform-specific implementation
            success = await self.platform.create_tunnel_interface(config)
            
            if not success:
                raise TunnelError("Platform tunnel creation failed")
            
            # Store configuration
            self.tunnel_configs[tunnel_id] = config
            self._save_tunnel_configs()
            
            # Create tunnel info
            tunnel_info = TunnelInfo(
                tunnel_id=tunnel_id,
                name=name,
                tunnel_type=TunnelType.SSH,
                status=TunnelStatus.ACTIVE,
                local_endpoint=f"127.0.0.1:{local_port}",
                remote_endpoint=f"{remote_host}:{remote_port}",
                created_at=datetime.utcnow(),
                last_connected=datetime.utcnow(),
                client_id=client_id,
                config=asdict(config)
            )
            
            self.active_tunnels[tunnel_id] = tunnel_info
            
            self.logger.info(f"SSH tunnel created: {tunnel_id} ({name})")
            return tunnel_id
            
        except Exception as e:
            self.logger.error(f"Failed to create SSH tunnel: {e}")
            raise TunnelError(f"SSH tunnel creation failed: {e}")
    
    async def create_openvpn_tunnel(self, name: str, config_file: str,
                                  client_id: str = None) -> str:
        """
        Create OpenVPN tunnel.
        
        Args:
            name: Tunnel name
            config_file: OpenVPN configuration file content
            client_id: Client ID for multi-tenant support
            
        Returns:
            str: Tunnel ID
            
        Raises:
            TunnelError: If tunnel creation fails
        """
        try:
            tunnel_id = self.generate_tunnel_id()
            
            # Save config file to temporary location
            config_path = self.config_dir / f"{tunnel_id}.ovpn"
            with open(config_path, 'w') as f:
                f.write(config_file)
            
            config_path.chmod(0o600)
            
            # Create tunnel configuration
            config = TunnelConfig(
                tunnel_type=TunnelType.OPENVPN,
                name=name,
                local_ip="",  # Will be assigned by OpenVPN
                remote_ip="",
                config_data={
                    'config_file': str(config_path)
                }
            )
            
            # Start OpenVPN process
            success = await self._start_openvpn_process(config_path)
            
            if not success:
                raise TunnelError("OpenVPN process start failed")
            
            # Store configuration
            self.tunnel_configs[tunnel_id] = config
            self._save_tunnel_configs()
            
            # Create tunnel info
            tunnel_info = TunnelInfo(
                tunnel_id=tunnel_id,
                name=name,
                tunnel_type=TunnelType.OPENVPN,
                status=TunnelStatus.ACTIVE,
                local_endpoint="tun0",  # OpenVPN interface
                remote_endpoint="",
                created_at=datetime.utcnow(),
                last_connected=datetime.utcnow(),
                client_id=client_id,
                config=asdict(config)
            )
            
            self.active_tunnels[tunnel_id] = tunnel_info
            
            self.logger.info(f"OpenVPN tunnel created: {tunnel_id} ({name})")
            return tunnel_id
            
        except Exception as e:
            self.logger.error(f"Failed to create OpenVPN tunnel: {e}")
            raise TunnelError(f"OpenVPN tunnel creation failed: {e}")
    
    async def destroy_tunnel(self, tunnel_id: str) -> bool:
        """
        Destroy a tunnel.
        
        Args:
            tunnel_id: Tunnel ID
            
        Returns:
            bool: True if tunnel was destroyed successfully
        """
        try:
            if tunnel_id not in self.active_tunnels:
                return False
            
            tunnel_info = self.active_tunnels[tunnel_id]
            
            # Destroy tunnel using platform-specific implementation
            success = await self.platform.destroy_tunnel_interface(tunnel_info.name)
            
            # Remove from active tunnels
            del self.active_tunnels[tunnel_id]
            
            # Remove configuration
            if tunnel_id in self.tunnel_configs:
                del self.tunnel_configs[tunnel_id]
                self._save_tunnel_configs()
            
            # Clean up OpenVPN config file if exists
            if tunnel_info.tunnel_type == TunnelType.OPENVPN:
                config_path = Path(tunnel_info.config.get('config_data', {}).get('config_file', ''))
                if config_path.exists():
                    config_path.unlink()
            
            self.logger.info(f"Tunnel destroyed: {tunnel_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to destroy tunnel {tunnel_id}: {e}")
            return False
    
    async def get_tunnel_status(self, tunnel_id: str) -> Optional[TunnelInfo]:
        """
        Get tunnel status.
        
        Args:
            tunnel_id: Tunnel ID
            
        Returns:
            Optional[TunnelInfo]: Tunnel information or None if not found
        """
        if tunnel_id not in self.active_tunnels:
            return None
        
        tunnel_info = self.active_tunnels[tunnel_id]
        
        # Update status by checking if tunnel is actually active
        try:
            active_tunnels = await self.platform.get_active_tunnels()
            
            # Check if tunnel is in active list
            tunnel_active = any(
                t.get('name') == tunnel_info.name for t in active_tunnels
            )
            
            if tunnel_active:
                tunnel_info.status = TunnelStatus.ACTIVE
                tunnel_info.last_connected = datetime.utcnow()
            else:
                tunnel_info.status = TunnelStatus.INACTIVE
            
        except Exception as e:
            self.logger.error(f"Failed to check tunnel status: {e}")
            tunnel_info.status = TunnelStatus.UNKNOWN
            tunnel_info.error_message = str(e)
        
        return tunnel_info
    
    async def list_tunnels(self, client_id: str = None) -> List[TunnelInfo]:
        """
        List all tunnels.
        
        Args:
            client_id: Filter by client ID (None for all)
            
        Returns:
            List[TunnelInfo]: List of tunnel information
        """
        tunnels = []
        
        for tunnel_id in list(self.active_tunnels.keys()):
            tunnel_info = await self.get_tunnel_status(tunnel_id)
            if tunnel_info:
                if client_id is None or tunnel_info.client_id == client_id:
                    tunnels.append(tunnel_info)
        
        return tunnels
    
    async def restart_tunnel(self, tunnel_id: str) -> bool:
        """
        Restart a tunnel.
        
        Args:
            tunnel_id: Tunnel ID
            
        Returns:
            bool: True if tunnel was restarted successfully
        """
        try:
            if tunnel_id not in self.active_tunnels:
                return False
            
            tunnel_info = self.active_tunnels[tunnel_id]
            config = self.tunnel_configs.get(tunnel_id)
            
            if not config:
                return False
            
            # Destroy existing tunnel
            await self.platform.destroy_tunnel_interface(tunnel_info.name)
            
            # Recreate tunnel
            success = await self.platform.create_tunnel_interface(config)
            
            if success:
                tunnel_info.status = TunnelStatus.ACTIVE
                tunnel_info.last_connected = datetime.utcnow()
                tunnel_info.error_message = None
            else:
                tunnel_info.status = TunnelStatus.ERROR
                tunnel_info.error_message = "Restart failed"
            
            self.logger.info(f"Tunnel restarted: {tunnel_id}")
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to restart tunnel {tunnel_id}: {e}")
            return False
    
    def _generate_wireguard_keys(self) -> tuple[str, str]:
        """Generate WireGuard key pair."""
        try:
            # Generate private key
            private_key_process = subprocess.run(
                ['wg', 'genkey'],
                capture_output=True,
                text=True,
                check=True
            )
            private_key = private_key_process.stdout.strip()
            
            # Generate public key from private key
            public_key_process = subprocess.run(
                ['wg', 'pubkey'],
                input=private_key,
                capture_output=True,
                text=True,
                check=True
            )
            public_key = public_key_process.stdout.strip()
            
            return private_key, public_key
            
        except subprocess.CalledProcessError as e:
            raise TunnelError(f"WireGuard key generation failed: {e}")
        except FileNotFoundError:
            raise TunnelError("WireGuard tools not found")
    
    def _get_available_tunnel_ip(self) -> str:
        """Get available IP address for tunnel."""
        # Use 10.8.0.x range for tunnels
        base_ip = "10.8.0."
        
        # Find available IP
        used_ips = set()
        for tunnel_info in self.active_tunnels.values():
            if tunnel_info.local_endpoint.startswith(base_ip):
                used_ips.add(tunnel_info.local_endpoint)
        
        for i in range(2, 255):  # Skip .0 and .1
            ip = f"{base_ip}{i}"
            if ip not in used_ips:
                return ip
        
        raise TunnelError("No available tunnel IP addresses")
    
    async def _start_openvpn_process(self, config_path: Path) -> bool:
        """Start OpenVPN process."""
        try:
            # Start OpenVPN in background
            process = await asyncio.create_subprocess_exec(
                'openvpn',
                '--config', str(config_path),
                '--daemon',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait a bit to see if it starts successfully
            await asyncio.sleep(2)
            
            # Check if process is still running
            if process.returncode is None:
                return True
            else:
                stdout, stderr = await process.communicate()
                self.logger.error(f"OpenVPN failed to start: {stderr.decode()}")
                return False
                
        except FileNotFoundError:
            raise TunnelError("OpenVPN not found")
        except Exception as e:
            self.logger.error(f"Failed to start OpenVPN: {e}")
            return False
    
    async def get_tunnel_statistics(self, tunnel_id: str) -> Dict[str, Any]:
        """
        Get tunnel statistics.
        
        Args:
            tunnel_id: Tunnel ID
            
        Returns:
            Dict[str, Any]: Tunnel statistics
        """
        if tunnel_id not in self.active_tunnels:
            return {}
        
        tunnel_info = self.active_tunnels[tunnel_id]
        
        try:
            if tunnel_info.tunnel_type == TunnelType.WIREGUARD:
                return await self._get_wireguard_stats(tunnel_info.name)
            elif tunnel_info.tunnel_type == TunnelType.SSH:
                return await self._get_ssh_tunnel_stats(tunnel_info.name)
            elif tunnel_info.tunnel_type == TunnelType.OPENVPN:
                return await self._get_openvpn_stats(tunnel_info.name)
        except Exception as e:
            self.logger.error(f"Failed to get tunnel statistics: {e}")
        
        return {}
    
    async def _get_wireguard_stats(self, interface_name: str) -> Dict[str, Any]:
        """Get WireGuard interface statistics."""
        try:
            result = subprocess.run(
                ['wg', 'show', interface_name, 'transfer'],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse output
            stats = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        peer = parts[0]
                        rx_bytes = int(parts[1])
                        tx_bytes = int(parts[2])
                        
                        stats[peer] = {
                            'rx_bytes': rx_bytes,
                            'tx_bytes': tx_bytes
                        }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get WireGuard stats: {e}")
            return {}
    
    async def _get_ssh_tunnel_stats(self, tunnel_name: str) -> Dict[str, Any]:
        """Get SSH tunnel statistics."""
        # SSH tunnels don't have built-in statistics
        # This would require monitoring the SSH process
        return {
            'status': 'active',
            'type': 'ssh'
        }
    
    async def _get_openvpn_stats(self, tunnel_name: str) -> Dict[str, Any]:
        """Get OpenVPN statistics."""
        # OpenVPN statistics would require parsing management interface
        # or log files - simplified implementation
        return {
            'status': 'active',
            'type': 'openvpn'
        }
    
    async def test_tunnel_connectivity(self, tunnel_id: str, target_host: str = None) -> bool:
        """
        Test tunnel connectivity.
        
        Args:
            tunnel_id: Tunnel ID
            target_host: Target host to ping through tunnel
            
        Returns:
            bool: True if tunnel is working
        """
        if tunnel_id not in self.active_tunnels:
            return False
        
        tunnel_info = self.active_tunnels[tunnel_id]
        
        try:
            # Default target based on tunnel type
            if target_host is None:
                if tunnel_info.tunnel_type == TunnelType.WIREGUARD:
                    target_host = tunnel_info.remote_endpoint.split(':')[0]
                elif tunnel_info.tunnel_type == TunnelType.SSH:
                    target_host = tunnel_info.config.get('config_data', {}).get('ssh_host')
                else:
                    target_host = "8.8.8.8"  # Fallback
            
            if not target_host:
                return False
            
            # Ping through tunnel
            from utils.network_scanner import NetworkScanner
            scanner = NetworkScanner()
            alive, _ = await scanner.ping_host(target_host)
            
            return alive
            
        except Exception as e:
            self.logger.error(f"Tunnel connectivity test failed: {e}")
            return False
    
    async def cleanup_inactive_tunnels(self) -> int:
        """
        Clean up inactive tunnels.
        
        Returns:
            int: Number of tunnels cleaned up
        """
        cleaned_count = 0
        
        for tunnel_id in list(self.active_tunnels.keys()):
            tunnel_info = await self.get_tunnel_status(tunnel_id)
            
            if tunnel_info and tunnel_info.status in [TunnelStatus.INACTIVE, TunnelStatus.ERROR]:
                # Check if tunnel has been inactive for too long
                if tunnel_info.last_connected:
                    inactive_time = datetime.utcnow() - tunnel_info.last_connected
                    if inactive_time.total_seconds() > 3600:  # 1 hour
                        await self.destroy_tunnel(tunnel_id)
                        cleaned_count += 1
        
        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} inactive tunnels")
        
        return cleaned_count
    
    def get_tunnel_manager_stats(self) -> Dict[str, Any]:
        """Get tunnel manager statistics."""
        active_count = len([t for t in self.active_tunnels.values() if t.status == TunnelStatus.ACTIVE])
        
        tunnel_types = {}
        for tunnel_info in self.active_tunnels.values():
            tunnel_type = tunnel_info.tunnel_type.value
            tunnel_types[tunnel_type] = tunnel_types.get(tunnel_type, 0) + 1
        
        return {
            'total_tunnels': len(self.active_tunnels),
            'active_tunnels': active_count,
            'tunnel_types': tunnel_types,
            'platform': self.platform.platform_name,
            'config_dir': str(self.config_dir)
        }