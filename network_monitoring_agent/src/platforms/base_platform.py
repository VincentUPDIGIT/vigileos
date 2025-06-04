"""
Base platform interface for cross-platform network monitoring agent.
Defines the common interface that all platform-specific implementations must follow.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum


class ServiceStatus(Enum):
    """Service status enumeration."""
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    UNKNOWN = "unknown"


class TunnelType(Enum):
    """Tunnel type enumeration."""
    WIREGUARD = "wireguard"
    SSH = "ssh"
    OPENVPN = "openvpn"


@dataclass
class SystemMetrics:
    """System metrics data structure."""
    cpu_percent: float
    memory_percent: float
    memory_total: int
    memory_used: int
    disk_percent: float
    disk_total: int
    disk_used: int
    load_average: Optional[List[float]] = None
    uptime: Optional[int] = None
    boot_time: Optional[int] = None


@dataclass
class NetworkInterface:
    """Network interface data structure."""
    name: str
    ip_addresses: List[str]
    mac_address: str
    status: str
    speed: Optional[int] = None
    mtu: Optional[int] = None
    rx_bytes: Optional[int] = None
    tx_bytes: Optional[int] = None
    rx_packets: Optional[int] = None
    tx_packets: Optional[int] = None


@dataclass
class ProcessInfo:
    """Process information data structure."""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    memory_rss: int
    status: str
    create_time: float
    cmdline: List[str]
    username: Optional[str] = None


@dataclass
class ServiceInfo:
    """Service information data structure."""
    name: str
    status: ServiceStatus
    enabled: bool
    description: Optional[str] = None
    pid: Optional[int] = None


@dataclass
class TunnelConfig:
    """Tunnel configuration data structure."""
    tunnel_type: TunnelType
    name: str
    local_ip: str
    remote_ip: str
    local_port: Optional[int] = None
    remote_port: Optional[int] = None
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    endpoint: Optional[str] = None
    allowed_ips: Optional[List[str]] = None
    config_data: Optional[Dict[str, Any]] = None


class BasePlatform(ABC):
    """
    Abstract base class for platform-specific implementations.
    
    This class defines the interface that all platform implementations
    (Linux, Windows, macOS) must implement to provide consistent
    cross-platform functionality.
    """

    def __init__(self):
        """Initialize the platform instance."""
        self.platform_name = self._get_platform_name()

    @abstractmethod
    def _get_platform_name(self) -> str:
        """Get the platform name."""
        pass

    # System Information Methods
    @abstractmethod
    def get_system_metrics(self) -> SystemMetrics:
        """
        Get comprehensive system metrics.
        
        Returns:
            SystemMetrics: CPU, memory, disk usage and other system metrics
            
        Raises:
            PlatformError: If metrics cannot be collected
        """
        pass

    @abstractmethod
    def get_network_interfaces(self) -> List[NetworkInterface]:
        """
        Get information about all network interfaces.
        
        Returns:
            List[NetworkInterface]: List of network interface information
            
        Raises:
            PlatformError: If interface information cannot be collected
        """
        pass

    @abstractmethod
    def get_running_processes(self, limit: Optional[int] = None) -> List[ProcessInfo]:
        """
        Get information about running processes.
        
        Args:
            limit: Maximum number of processes to return (None for all)
            
        Returns:
            List[ProcessInfo]: List of process information
            
        Raises:
            PlatformError: If process information cannot be collected
        """
        pass

    @abstractmethod
    def get_system_services(self) -> List[ServiceInfo]:
        """
        Get information about system services.
        
        Returns:
            List[ServiceInfo]: List of service information
            
        Raises:
            PlatformError: If service information cannot be collected
        """
        pass

    # Service Management Methods
    @abstractmethod
    def install_service(self, service_config: Dict[str, Any]) -> bool:
        """
        Install a system service.
        
        Args:
            service_config: Service configuration dictionary
            
        Returns:
            bool: True if service was installed successfully
            
        Raises:
            PlatformError: If service installation fails
        """
        pass

    @abstractmethod
    def start_service(self, service_name: str) -> bool:
        """
        Start a system service.
        
        Args:
            service_name: Name of the service to start
            
        Returns:
            bool: True if service was started successfully
            
        Raises:
            PlatformError: If service cannot be started
        """
        pass

    @abstractmethod
    def stop_service(self, service_name: str) -> bool:
        """
        Stop a system service.
        
        Args:
            service_name: Name of the service to stop
            
        Returns:
            bool: True if service was stopped successfully
            
        Raises:
            PlatformError: If service cannot be stopped
        """
        pass

    @abstractmethod
    def get_service_status(self, service_name: str) -> ServiceStatus:
        """
        Get the status of a system service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            ServiceStatus: Current status of the service
            
        Raises:
            PlatformError: If service status cannot be determined
        """
        pass

    # Network/Tunnel Management Methods
    @abstractmethod
    def create_tunnel_interface(self, config: TunnelConfig) -> bool:
        """
        Create a network tunnel interface.
        
        Args:
            config: Tunnel configuration
            
        Returns:
            bool: True if tunnel was created successfully
            
        Raises:
            PlatformError: If tunnel creation fails
        """
        pass

    @abstractmethod
    def destroy_tunnel_interface(self, tunnel_name: str) -> bool:
        """
        Destroy a network tunnel interface.
        
        Args:
            tunnel_name: Name of the tunnel to destroy
            
        Returns:
            bool: True if tunnel was destroyed successfully
            
        Raises:
            PlatformError: If tunnel destruction fails
        """
        pass

    @abstractmethod
    def get_active_tunnels(self) -> List[Dict[str, Any]]:
        """
        Get information about active tunnels.
        
        Returns:
            List[Dict[str, Any]]: List of active tunnel information
            
        Raises:
            PlatformError: If tunnel information cannot be collected
        """
        pass

    # File System Methods
    @abstractmethod
    def get_default_config_path(self) -> Path:
        """
        Get the default configuration directory path for this platform.
        
        Returns:
            Path: Default configuration directory path
        """
        pass

    @abstractmethod
    def get_default_log_path(self) -> Path:
        """
        Get the default log directory path for this platform.
        
        Returns:
            Path: Default log directory path
        """
        pass

    @abstractmethod
    def get_service_config_path(self) -> Path:
        """
        Get the service configuration file path for this platform.
        
        Returns:
            Path: Service configuration file path
        """
        pass

    @abstractmethod
    def get_temp_path(self) -> Path:
        """
        Get the temporary directory path for this platform.
        
        Returns:
            Path: Temporary directory path
        """
        pass

    # Security Methods
    @abstractmethod
    def set_file_permissions(self, file_path: Path, permissions: Union[str, int]) -> bool:
        """
        Set file permissions in a platform-appropriate way.
        
        Args:
            file_path: Path to the file
            permissions: Permissions to set (platform-specific format)
            
        Returns:
            bool: True if permissions were set successfully
            
        Raises:
            PlatformError: If permissions cannot be set
        """
        pass

    @abstractmethod
    def create_secure_directory(self, dir_path: Path, owner: Optional[str] = None) -> bool:
        """
        Create a directory with secure permissions.
        
        Args:
            dir_path: Path to the directory to create
            owner: Owner of the directory (None for current user)
            
        Returns:
            bool: True if directory was created successfully
            
        Raises:
            PlatformError: If directory creation fails
        """
        pass

    # Firewall Methods
    @abstractmethod
    def get_firewall_rules(self) -> List[Dict[str, Any]]:
        """
        Get current firewall rules.
        
        Returns:
            List[Dict[str, Any]]: List of firewall rules
            
        Raises:
            PlatformError: If firewall rules cannot be retrieved
        """
        pass

    @abstractmethod
    def add_firewall_rule(self, rule_config: Dict[str, Any]) -> bool:
        """
        Add a firewall rule.
        
        Args:
            rule_config: Firewall rule configuration
            
        Returns:
            bool: True if rule was added successfully
            
        Raises:
            PlatformError: If firewall rule cannot be added
        """
        pass

    # Command Execution Methods
    @abstractmethod
    def execute_command(self, command: Union[str, List[str]], 
                       timeout: Optional[int] = None,
                       capture_output: bool = True) -> Dict[str, Any]:
        """
        Execute a system command.
        
        Args:
            command: Command to execute (string or list of arguments)
            timeout: Command timeout in seconds
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            Dict[str, Any]: Command execution result with returncode, stdout, stderr
            
        Raises:
            PlatformError: If command execution fails
        """
        pass

    # Utility Methods
    def is_admin(self) -> bool:
        """
        Check if the current process has administrative privileges.
        
        Returns:
            bool: True if running with admin privileges
        """
        try:
            return self._check_admin_privileges()
        except Exception:
            return False

    @abstractmethod
    def _check_admin_privileges(self) -> bool:
        """Platform-specific admin privilege check."""
        pass

    def get_platform_info(self) -> Dict[str, Any]:
        """
        Get comprehensive platform information.
        
        Returns:
            Dict[str, Any]: Platform information including OS, version, architecture
        """
        return {
            'platform': self.platform_name,
            'is_admin': self.is_admin(),
            'config_path': str(self.get_default_config_path()),
            'log_path': str(self.get_default_log_path()),
            'temp_path': str(self.get_temp_path())
        }


class PlatformError(Exception):
    """Exception raised for platform-specific errors."""
    
    def __init__(self, message: str, platform: str = None, error_code: int = None):
        self.message = message
        self.platform = platform
        self.error_code = error_code
        super().__init__(self.message)

    def __str__(self):
        error_str = f"PlatformError: {self.message}"
        if self.platform:
            error_str += f" (Platform: {self.platform})"
        if self.error_code:
            error_str += f" (Code: {self.error_code})"
        return error_str