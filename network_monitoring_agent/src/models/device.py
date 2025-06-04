"""
Device model for network monitoring.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class DeviceType(Enum):
    """Device type enumeration."""
    ROUTER = "router"
    SWITCH = "switch"
    FIREWALL = "firewall"
    ACCESS_POINT = "access_point"
    SERVER = "server"
    WORKSTATION = "workstation"
    PRINTER = "printer"
    IOT_DEVICE = "iot_device"
    STORAGE = "storage"
    LOAD_BALANCER = "load_balancer"
    VPN_GATEWAY = "vpn_gateway"
    UNKNOWN = "unknown"


class DeviceStatus(Enum):
    """Device status enumeration."""
    ONLINE = "online"
    OFFLINE = "offline"
    WARNING = "warning"
    CRITICAL = "critical"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


@dataclass
class DeviceCredentials:
    """Device authentication credentials."""
    username: Optional[str] = None
    password: Optional[str] = None
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    api_key: Optional[str] = None
    token: Optional[str] = None
    certificate: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)."""
        return {
            'username': self.username,
            'has_password': bool(self.password),
            'has_private_key': bool(self.private_key),
            'has_public_key': bool(self.public_key),
            'has_api_key': bool(self.api_key),
            'has_token': bool(self.token),
            'has_certificate': bool(self.certificate)
        }


@dataclass
class SNMPConfig:
    """SNMP configuration."""
    community: str = "public"
    version: str = "2c"  # 1, 2c, 3
    port: int = 161
    timeout: int = 5
    retries: int = 3
    # SNMPv3 specific
    username: Optional[str] = None
    auth_protocol: Optional[str] = None  # MD5, SHA
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None  # DES, AES
    priv_password: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class SSHConfig:
    """SSH configuration."""
    username: str
    password: Optional[str] = None
    private_key: Optional[str] = None
    port: int = 22
    timeout: int = 30
    key_type: str = "rsa"  # rsa, ed25519, ecdsa
    strict_host_key_checking: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)."""
        return {
            'username': self.username,
            'has_password': bool(self.password),
            'has_private_key': bool(self.private_key),
            'port': self.port,
            'timeout': self.timeout,
            'key_type': self.key_type,
            'strict_host_key_checking': self.strict_host_key_checking
        }


@dataclass
class WebConfig:
    """Web interface configuration."""
    base_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    auth_token: Optional[str] = None
    verify_ssl: bool = True
    timeout: int = 30
    user_agent: str = "NetworkMonitoringAgent/1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)."""
        return {
            'base_url': self.base_url,
            'username': self.username,
            'has_password': bool(self.password),
            'has_auth_token': bool(self.auth_token),
            'verify_ssl': self.verify_ssl,
            'timeout': self.timeout,
            'user_agent': self.user_agent
        }


@dataclass
class APIConfig:
    """REST API configuration."""
    base_url: str
    auth_token: Optional[str] = None
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    verify_ssl: bool = True
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)."""
        return {
            'base_url': self.base_url,
            'has_auth_token': bool(self.auth_token),
            'has_api_key': bool(self.api_key),
            'username': self.username,
            'has_password': bool(self.password),
            'headers': self.headers,
            'timeout': self.timeout,
            'verify_ssl': self.verify_ssl,
            'endpoints': self.endpoints
        }


@dataclass
class Device:
    """
    Network device model.
    
    Represents a network device that can be monitored using various protocols.
    """
    device_id: str
    name: str
    device_type: DeviceType
    ip_address: str
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    serial_number: Optional[str] = None
    
    # Status and monitoring
    status: DeviceStatus = DeviceStatus.UNKNOWN
    last_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Configuration for different protocols
    snmp_config: Optional[SNMPConfig] = None
    ssh_config: Optional[SSHConfig] = None
    web_config: Optional[WebConfig] = None
    api_config: Optional[APIConfig] = None
    
    # Monitoring settings
    monitoring_enabled: bool = True
    collection_interval: int = 60  # seconds
    timeout: int = 30  # seconds
    retry_attempts: int = 3
    
    # Tags and metadata
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Network information
    subnet: Optional[str] = None
    vlan_id: Optional[int] = None
    port_count: Optional[int] = None
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()
    
    def update_status(self, status: DeviceStatus, timestamp: Optional[datetime] = None):
        """Update device status."""
        self.status = status
        self.last_updated = timestamp or datetime.utcnow()
        if status in [DeviceStatus.ONLINE, DeviceStatus.WARNING]:
            self.last_seen = self.last_updated
    
    def is_online(self) -> bool:
        """Check if device is online."""
        return self.status == DeviceStatus.ONLINE
    
    def is_monitoring_enabled(self) -> bool:
        """Check if monitoring is enabled for this device."""
        return self.monitoring_enabled
    
    def get_primary_protocol(self) -> Optional[str]:
        """Get the primary monitoring protocol for this device."""
        if self.snmp_config:
            return "snmp"
        elif self.ssh_config:
            return "ssh"
        elif self.api_config:
            return "api"
        elif self.web_config:
            return "web"
        return None
    
    def get_available_protocols(self) -> List[str]:
        """Get list of available monitoring protocols."""
        protocols = []
        if self.snmp_config:
            protocols.append("snmp")
        if self.ssh_config:
            protocols.append("ssh")
        if self.web_config:
            protocols.append("web")
        if self.api_config:
            protocols.append("api")
        return protocols
    
    def add_tag(self, key: str, value: str):
        """Add a tag to the device."""
        self.tags[key] = value
        self.last_updated = datetime.utcnow()
    
    def remove_tag(self, key: str) -> bool:
        """Remove a tag from the device."""
        if key in self.tags:
            del self.tags[key]
            self.last_updated = datetime.utcnow()
            return True
        return False
    
    def get_tag(self, key: str, default: str = None) -> Optional[str]:
        """Get a tag value."""
        return self.tags.get(key, default)
    
    def set_metadata(self, key: str, value: Any):
        """Set metadata value."""
        self.metadata[key] = value
        self.last_updated = datetime.utcnow()
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        return self.metadata.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert device to dictionary."""
        data = {
            'device_id': self.device_id,
            'name': self.name,
            'device_type': self.device_type.value,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'hostname': self.hostname,
            'description': self.description,
            'location': self.location,
            'vendor': self.vendor,
            'model': self.model,
            'firmware_version': self.firmware_version,
            'serial_number': self.serial_number,
            'status': self.status.value,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'created_at': self.created_at.isoformat(),
            'monitoring_enabled': self.monitoring_enabled,
            'collection_interval': self.collection_interval,
            'timeout': self.timeout,
            'retry_attempts': self.retry_attempts,
            'tags': self.tags,
            'metadata': self.metadata,
            'subnet': self.subnet,
            'vlan_id': self.vlan_id,
            'port_count': self.port_count,
            'available_protocols': self.get_available_protocols(),
            'primary_protocol': self.get_primary_protocol()
        }
        
        # Add configuration info (without sensitive data)
        if self.snmp_config:
            data['snmp_config'] = self.snmp_config.to_dict()
        if self.ssh_config:
            data['ssh_config'] = self.ssh_config.to_dict()
        if self.web_config:
            data['web_config'] = self.web_config.to_dict()
        if self.api_config:
            data['api_config'] = self.api_config.to_dict()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Device':
        """Create device from dictionary."""
        # Parse datetime fields
        if 'last_seen' in data and data['last_seen']:
            data['last_seen'] = datetime.fromisoformat(data['last_seen'])
        if 'last_updated' in data and data['last_updated']:
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        
        # Parse enum fields
        if 'device_type' in data:
            data['device_type'] = DeviceType(data['device_type'])
        if 'status' in data:
            data['status'] = DeviceStatus(data['status'])
        
        # Parse configuration objects
        if 'snmp_config' in data and data['snmp_config']:
            data['snmp_config'] = SNMPConfig(**data['snmp_config'])
        if 'ssh_config' in data and data['ssh_config']:
            # Remove non-constructor fields
            ssh_data = data['ssh_config'].copy()
            ssh_data.pop('has_password', None)
            ssh_data.pop('has_private_key', None)
            data['ssh_config'] = SSHConfig(**ssh_data)
        if 'web_config' in data and data['web_config']:
            # Remove non-constructor fields
            web_data = data['web_config'].copy()
            web_data.pop('has_password', None)
            web_data.pop('has_auth_token', None)
            data['web_config'] = WebConfig(**web_data)
        if 'api_config' in data and data['api_config']:
            # Remove non-constructor fields
            api_data = data['api_config'].copy()
            api_data.pop('has_auth_token', None)
            api_data.pop('has_api_key', None)
            api_data.pop('has_password', None)
            data['api_config'] = APIConfig(**api_data)
        
        # Remove computed fields
        data.pop('available_protocols', None)
        data.pop('primary_protocol', None)
        
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert device to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Device':
        """Create device from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def clone(self, new_device_id: str = None) -> 'Device':
        """Create a copy of the device."""
        data = self.to_dict()
        if new_device_id:
            data['device_id'] = new_device_id
        data['created_at'] = datetime.utcnow().isoformat()
        data['last_updated'] = datetime.utcnow().isoformat()
        return self.from_dict(data)
    
    def validate(self) -> List[str]:
        """Validate device configuration and return list of errors."""
        errors = []
        
        # Required fields
        if not self.device_id:
            errors.append("device_id is required")
        if not self.name:
            errors.append("name is required")
        if not self.ip_address:
            errors.append("ip_address is required")
        
        # IP address validation
        if self.ip_address:
            try:
                import ipaddress
                ipaddress.ip_address(self.ip_address)
            except ValueError:
                errors.append("invalid ip_address format")
        
        # MAC address validation
        if self.mac_address:
            import re
            mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
            if not mac_pattern.match(self.mac_address):
                errors.append("invalid mac_address format")
        
        # Protocol configuration validation
        if not any([self.snmp_config, self.ssh_config, self.web_config, self.api_config]):
            errors.append("at least one monitoring protocol must be configured")
        
        # SNMP validation
        if self.snmp_config:
            if self.snmp_config.version not in ['1', '2c', '3']:
                errors.append("invalid SNMP version")
            if self.snmp_config.version == '3' and not self.snmp_config.username:
                errors.append("SNMPv3 requires username")
        
        # SSH validation
        if self.ssh_config:
            if not self.ssh_config.username:
                errors.append("SSH requires username")
            if not self.ssh_config.password and not self.ssh_config.private_key:
                errors.append("SSH requires either password or private key")
        
        # Web validation
        if self.web_config:
            if not self.web_config.base_url:
                errors.append("Web config requires base_url")
        
        # API validation
        if self.api_config:
            if not self.api_config.base_url:
                errors.append("API config requires base_url")
        
        return errors
    
    def is_valid(self) -> bool:
        """Check if device configuration is valid."""
        return len(self.validate()) == 0
    
    def __str__(self) -> str:
        """String representation of device."""
        return f"Device({self.device_id}, {self.name}, {self.device_type.value}, {self.ip_address})"
    
    def __repr__(self) -> str:
        """Detailed string representation of device."""
        return (f"Device(device_id='{self.device_id}', name='{self.name}', "
                f"device_type={self.device_type}, ip_address='{self.ip_address}', "
                f"status={self.status})")
    
    def __eq__(self, other) -> bool:
        """Check equality based on device_id."""
        if not isinstance(other, Device):
            return False
        return self.device_id == other.device_id
    
    def __hash__(self) -> int:
        """Hash based on device_id."""
        return hash(self.device_id)