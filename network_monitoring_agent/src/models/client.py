"""
Client model for multi-tenant monitoring.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class ClientStatus(Enum):
    """Client status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class ClientType(Enum):
    """Client type enumeration."""
    ENTERPRISE = "enterprise"
    SMB = "smb"
    INDIVIDUAL = "individual"
    TRIAL = "trial"
    INTERNAL = "internal"


@dataclass
class ClientQuota:
    """Client resource quota configuration."""
    max_devices: Optional[int] = None
    max_metrics_per_hour: Optional[int] = None
    max_storage_mb: Optional[int] = None
    max_api_calls_per_hour: Optional[int] = None
    max_tunnels: Optional[int] = None
    retention_days: int = 30
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def is_within_limits(self, current_usage: Dict[str, int]) -> bool:
        """Check if current usage is within quota limits."""
        if self.max_devices and current_usage.get('devices', 0) > self.max_devices:
            return False
        if self.max_metrics_per_hour and current_usage.get('metrics_per_hour', 0) > self.max_metrics_per_hour:
            return False
        if self.max_storage_mb and current_usage.get('storage_mb', 0) > self.max_storage_mb:
            return False
        if self.max_api_calls_per_hour and current_usage.get('api_calls_per_hour', 0) > self.max_api_calls_per_hour:
            return False
        if self.max_tunnels and current_usage.get('tunnels', 0) > self.max_tunnels:
            return False
        return True


@dataclass
class ClientSettings:
    """Client-specific settings."""
    timezone: str = "UTC"
    date_format: str = "ISO"
    number_format: str = "US"
    language: str = "en"
    theme: str = "default"
    notifications_enabled: bool = True
    email_notifications: bool = True
    sms_notifications: bool = False
    webhook_url: Optional[str] = None
    custom_dashboard: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class Client:
    """
    Client model for multi-tenant monitoring.
    
    Represents a client/tenant in the monitoring system with their
    own devices, metrics, and configuration.
    """
    client_id: str
    name: str
    client_type: ClientType
    contact_email: str
    
    # Optional information
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    
    # Status and lifecycle
    status: ClientStatus = ClientStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    # Configuration
    quota: ClientQuota = field(default_factory=ClientQuota)
    settings: ClientSettings = field(default_factory=ClientSettings)
    
    # Security and access
    api_key: Optional[str] = None
    allowed_ips: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    
    # Billing and subscription
    subscription_plan: Optional[str] = None
    billing_email: Optional[str] = None
    payment_method: Optional[str] = None
    next_billing_date: Optional[datetime] = None
    
    # Metadata and tags
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Usage tracking
    device_count: int = 0
    total_metrics: int = 0
    storage_used_mb: float = 0.0
    last_metric_timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        """Post-initialization processing."""
        # Set default permissions based on client type
        if not self.permissions:
            if self.client_type == ClientType.ENTERPRISE:
                self.permissions = [
                    'devices:read', 'devices:write', 'devices:delete',
                    'metrics:read', 'metrics:write',
                    'tunnels:read', 'tunnels:write',
                    'alerts:read', 'alerts:write',
                    'reports:read', 'reports:write'
                ]
            elif self.client_type == ClientType.SMB:
                self.permissions = [
                    'devices:read', 'devices:write',
                    'metrics:read', 'metrics:write',
                    'tunnels:read', 'tunnels:write',
                    'alerts:read'
                ]
            elif self.client_type == ClientType.TRIAL:
                self.permissions = [
                    'devices:read', 'devices:write',
                    'metrics:read',
                    'tunnels:read'
                ]
            else:
                self.permissions = ['devices:read', 'metrics:read']
        
        # Set default quota based on client type
        if self.client_type == ClientType.ENTERPRISE:
            if self.quota.max_devices is None:
                self.quota.max_devices = 1000
            if self.quota.max_metrics_per_hour is None:
                self.quota.max_metrics_per_hour = 100000
            if self.quota.max_storage_mb is None:
                self.quota.max_storage_mb = 10000
            if self.quota.max_tunnels is None:
                self.quota.max_tunnels = 50
        elif self.client_type == ClientType.SMB:
            if self.quota.max_devices is None:
                self.quota.max_devices = 100
            if self.quota.max_metrics_per_hour is None:
                self.quota.max_metrics_per_hour = 10000
            if self.quota.max_storage_mb is None:
                self.quota.max_storage_mb = 1000
            if self.quota.max_tunnels is None:
                self.quota.max_tunnels = 10
        elif self.client_type == ClientType.TRIAL:
            if self.quota.max_devices is None:
                self.quota.max_devices = 10
            if self.quota.max_metrics_per_hour is None:
                self.quota.max_metrics_per_hour = 1000
            if self.quota.max_storage_mb is None:
                self.quota.max_storage_mb = 100
            if self.quota.max_tunnels is None:
                self.quota.max_tunnels = 2
            self.quota.retention_days = 7
    
    def activate(self):
        """Activate the client."""
        self.status = ClientStatus.ACTIVE
        self.activated_at = datetime.utcnow()
    
    def suspend(self):
        """Suspend the client."""
        self.status = ClientStatus.SUSPENDED
    
    def deactivate(self):
        """Deactivate the client."""
        self.status = ClientStatus.INACTIVE
    
    def is_active(self) -> bool:
        """Check if client is active."""
        return self.status == ClientStatus.ACTIVE
    
    def is_suspended(self) -> bool:
        """Check if client is suspended."""
        return self.status == ClientStatus.SUSPENDED
    
    def update_last_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login = datetime.utcnow()
        self.update_last_activity()
    
    def has_permission(self, permission: str) -> bool:
        """Check if client has a specific permission."""
        return permission in self.permissions
    
    def add_permission(self, permission: str):
        """Add a permission to the client."""
        if permission not in self.permissions:
            self.permissions.append(permission)
    
    def remove_permission(self, permission: str) -> bool:
        """Remove a permission from the client."""
        if permission in self.permissions:
            self.permissions.remove(permission)
            return True
        return False
    
    def add_tag(self, key: str, value: str):
        """Add a tag to the client."""
        self.tags[key] = value
    
    def remove_tag(self, key: str) -> bool:
        """Remove a tag from the client."""
        if key in self.tags:
            del self.tags[key]
            return True
        return False
    
    def get_tag(self, key: str, default: str = None) -> Optional[str]:
        """Get a tag value."""
        return self.tags.get(key, default)
    
    def set_metadata(self, key: str, value: Any):
        """Set metadata value."""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        return self.metadata.get(key, default)
    
    def update_usage_stats(self, device_count: int = None, 
                          total_metrics: int = None,
                          storage_used_mb: float = None,
                          last_metric_timestamp: datetime = None):
        """Update usage statistics."""
        if device_count is not None:
            self.device_count = device_count
        if total_metrics is not None:
            self.total_metrics = total_metrics
        if storage_used_mb is not None:
            self.storage_used_mb = storage_used_mb
        if last_metric_timestamp is not None:
            self.last_metric_timestamp = last_metric_timestamp
        
        self.update_last_activity()
    
    def get_current_usage(self) -> Dict[str, Any]:
        """Get current resource usage."""
        return {
            'devices': self.device_count,
            'total_metrics': self.total_metrics,
            'storage_mb': self.storage_used_mb,
            'last_metric_timestamp': self.last_metric_timestamp.isoformat() if self.last_metric_timestamp else None
        }
    
    def is_within_quota(self, usage_override: Dict[str, int] = None) -> bool:
        """Check if current usage is within quota limits."""
        usage = usage_override or {
            'devices': self.device_count,
            'storage_mb': int(self.storage_used_mb)
        }
        return self.quota.is_within_limits(usage)
    
    def get_quota_usage_percentage(self) -> Dict[str, float]:
        """Get quota usage as percentages."""
        percentages = {}
        
        if self.quota.max_devices:
            percentages['devices'] = (self.device_count / self.quota.max_devices) * 100
        
        if self.quota.max_storage_mb:
            percentages['storage'] = (self.storage_used_mb / self.quota.max_storage_mb) * 100
        
        return percentages
    
    def is_trial_expired(self, trial_duration_days: int = 30) -> bool:
        """Check if trial period has expired."""
        if self.client_type != ClientType.TRIAL:
            return False
        
        if not self.activated_at:
            return False
        
        trial_end = self.activated_at.replace(day=self.activated_at.day + trial_duration_days)
        return datetime.utcnow() > trial_end
    
    def get_days_since_last_activity(self) -> Optional[int]:
        """Get number of days since last activity."""
        if not self.last_activity:
            return None
        
        delta = datetime.utcnow() - self.last_activity
        return delta.days
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert client to dictionary."""
        data = {
            'client_id': self.client_id,
            'name': self.name,
            'client_type': self.client_type.value,
            'contact_email': self.contact_email,
            'company_name': self.company_name,
            'contact_name': self.contact_name,
            'contact_phone': self.contact_phone,
            'address': self.address,
            'website': self.website,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'activated_at': self.activated_at.isoformat() if self.activated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'quota': self.quota.to_dict(),
            'settings': self.settings.to_dict(),
            'api_key': self.api_key,
            'allowed_ips': self.allowed_ips,
            'permissions': self.permissions,
            'subscription_plan': self.subscription_plan,
            'billing_email': self.billing_email,
            'payment_method': self.payment_method,
            'next_billing_date': self.next_billing_date.isoformat() if self.next_billing_date else None,
            'tags': self.tags,
            'metadata': self.metadata,
            'device_count': self.device_count,
            'total_metrics': self.total_metrics,
            'storage_used_mb': self.storage_used_mb,
            'last_metric_timestamp': self.last_metric_timestamp.isoformat() if self.last_metric_timestamp else None
        }
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Client':
        """Create client from dictionary."""
        # Parse datetime fields
        datetime_fields = ['created_at', 'activated_at', 'last_login', 'last_activity', 
                          'next_billing_date', 'last_metric_timestamp']
        for field in datetime_fields:
            if field in data and data[field]:
                data[field] = datetime.fromisoformat(data[field])
        
        # Parse enum fields
        if 'client_type' in data:
            data['client_type'] = ClientType(data['client_type'])
        if 'status' in data:
            data['status'] = ClientStatus(data['status'])
        
        # Parse nested objects
        if 'quota' in data and data['quota']:
            data['quota'] = ClientQuota(**data['quota'])
        if 'settings' in data and data['settings']:
            data['settings'] = ClientSettings(**data['settings'])
        
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert client to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Client':
        """Create client from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def clone(self, new_client_id: str = None) -> 'Client':
        """Create a copy of the client."""
        data = self.to_dict()
        if new_client_id:
            data['client_id'] = new_client_id
        data['created_at'] = datetime.utcnow().isoformat()
        data['activated_at'] = None
        data['last_login'] = None
        data['last_activity'] = None
        data['status'] = ClientStatus.PENDING.value
        return self.from_dict(data)
    
    def validate(self) -> List[str]:
        """Validate client configuration and return list of errors."""
        errors = []
        
        # Required fields
        if not self.client_id:
            errors.append("client_id is required")
        if not self.name:
            errors.append("name is required")
        if not self.contact_email:
            errors.append("contact_email is required")
        
        # Email validation
        if self.contact_email:
            import re
            email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
            if not email_pattern.match(self.contact_email):
                errors.append("invalid contact_email format")
        
        # Billing email validation
        if self.billing_email:
            import re
            email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
            if not email_pattern.match(self.billing_email):
                errors.append("invalid billing_email format")
        
        # Phone validation (basic)
        if self.contact_phone:
            import re
            phone_pattern = re.compile(r'^[\+]?[1-9][\d\s\-\(\)]{7,15}$')
            if not phone_pattern.match(self.contact_phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')):
                errors.append("invalid contact_phone format")
        
        # Website validation
        if self.website:
            import re
            url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$')
            if not url_pattern.match(self.website):
                errors.append("invalid website URL format")
        
        # IP address validation
        for ip in self.allowed_ips:
            try:
                import ipaddress
                ipaddress.ip_address(ip)
            except ValueError:
                errors.append(f"invalid IP address: {ip}")
        
        return errors
    
    def is_valid(self) -> bool:
        """Check if client configuration is valid."""
        return len(self.validate()) == 0
    
    def __str__(self) -> str:
        """String representation of client."""
        return f"Client({self.client_id}, {self.name}, {self.client_type.value})"
    
    def __repr__(self) -> str:
        """Detailed string representation of client."""
        return (f"Client(client_id='{self.client_id}', name='{self.name}', "
                f"client_type={self.client_type}, status={self.status})")
    
    def __eq__(self, other) -> bool:
        """Check equality based on client_id."""
        if not isinstance(other, Client):
            return False
        return self.client_id == other.client_id
    
    def __hash__(self) -> int:
        """Hash based on client_id."""
        return hash(self.client_id)