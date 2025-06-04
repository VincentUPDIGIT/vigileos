"""
Metric model for network monitoring data.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum


class MetricType(Enum):
    """Metric type enumeration."""
    PERFORMANCE = "performance"  # CPU, memory, disk usage
    NETWORK = "network"         # Interface stats, bandwidth, latency
    SYSTEM = "system"           # Uptime, temperature, power
    SECURITY = "security"       # Failed logins, firewall events
    APPLICATION = "application" # App-specific metrics
    CUSTOM = "custom"           # User-defined metrics
    HEALTH = "health"           # Device health indicators
    AVAILABILITY = "availability" # Up/down status


class MetricSeverity(Enum):
    """Metric severity level."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


@dataclass
class MetricThreshold:
    """Metric threshold configuration."""
    warning_min: Optional[float] = None
    warning_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    
    def check_value(self, value: float) -> MetricSeverity:
        """Check value against thresholds and return severity."""
        if self.critical_min is not None and value < self.critical_min:
            return MetricSeverity.CRITICAL
        if self.critical_max is not None and value > self.critical_max:
            return MetricSeverity.CRITICAL
        if self.warning_min is not None and value < self.warning_min:
            return MetricSeverity.WARNING
        if self.warning_max is not None and value > self.warning_max:
            return MetricSeverity.WARNING
        return MetricSeverity.INFO
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class Metric:
    """
    Network monitoring metric.
    
    Represents a single metric data point collected from a device.
    """
    device_id: str
    metric_type: MetricType
    name: str
    value: Union[float, int, str, bool]
    unit: str
    timestamp: datetime
    
    # Optional fields
    description: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Quality indicators
    quality: float = 1.0  # 0.0 to 1.0, where 1.0 is perfect quality
    source: Optional[str] = None  # Collection source (snmp, ssh, api, etc.)
    
    # Threshold and alerting
    threshold: Optional[MetricThreshold] = None
    severity: Optional[MetricSeverity] = None
    
    # Aggregation support
    sample_count: int = 1
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    sum_value: Optional[float] = None
    
    def __post_init__(self):
        """Post-initialization processing."""
        # Auto-calculate severity if threshold is set
        if self.threshold and isinstance(self.value, (int, float)):
            self.severity = self.threshold.check_value(float(self.value))
        
        # Set min/max/sum for single values
        if isinstance(self.value, (int, float)) and self.sample_count == 1:
            if self.min_value is None:
                self.min_value = float(self.value)
            if self.max_value is None:
                self.max_value = float(self.value)
            if self.sum_value is None:
                self.sum_value = float(self.value)
    
    def get_numeric_value(self) -> Optional[float]:
        """Get numeric value if possible."""
        if isinstance(self.value, (int, float)):
            return float(self.value)
        elif isinstance(self.value, str):
            try:
                return float(self.value)
            except ValueError:
                return None
        elif isinstance(self.value, bool):
            return 1.0 if self.value else 0.0
        return None
    
    def get_average_value(self) -> Optional[float]:
        """Get average value for aggregated metrics."""
        if self.sample_count > 0 and self.sum_value is not None:
            return self.sum_value / self.sample_count
        return self.get_numeric_value()
    
    def is_numeric(self) -> bool:
        """Check if metric value is numeric."""
        return isinstance(self.value, (int, float))
    
    def is_boolean(self) -> bool:
        """Check if metric value is boolean."""
        return isinstance(self.value, bool)
    
    def is_string(self) -> bool:
        """Check if metric value is string."""
        return isinstance(self.value, str)
    
    def add_tag(self, key: str, value: str):
        """Add a tag to the metric."""
        self.tags[key] = value
    
    def get_tag(self, key: str, default: str = None) -> Optional[str]:
        """Get a tag value."""
        return self.tags.get(key, default)
    
    def set_metadata(self, key: str, value: Any):
        """Set metadata value."""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        return self.metadata.get(key, default)
    
    def set_threshold(self, warning_min: float = None, warning_max: float = None,
                     critical_min: float = None, critical_max: float = None):
        """Set threshold values."""
        self.threshold = MetricThreshold(
            warning_min=warning_min,
            warning_max=warning_max,
            critical_min=critical_min,
            critical_max=critical_max
        )
        # Recalculate severity
        if isinstance(self.value, (int, float)):
            self.severity = self.threshold.check_value(float(self.value))
    
    def is_warning(self) -> bool:
        """Check if metric is in warning state."""
        return self.severity == MetricSeverity.WARNING
    
    def is_critical(self) -> bool:
        """Check if metric is in critical state."""
        return self.severity in [MetricSeverity.CRITICAL, MetricSeverity.FATAL]
    
    def is_healthy(self) -> bool:
        """Check if metric is in healthy state."""
        return self.severity == MetricSeverity.INFO
    
    def get_full_name(self) -> str:
        """Get full metric name including device ID."""
        return f"{self.device_id}.{self.name}"
    
    def get_display_value(self) -> str:
        """Get formatted display value with unit."""
        if isinstance(self.value, float):
            if self.unit in ['percent', '%']:
                return f"{self.value:.1f}%"
            elif self.unit in ['bytes', 'B']:
                return self._format_bytes(self.value)
            elif self.unit in ['seconds', 's']:
                return self._format_duration(self.value)
            else:
                return f"{self.value:.2f} {self.unit}"
        else:
            return f"{self.value} {self.unit}" if self.unit else str(self.value)
    
    def _format_bytes(self, bytes_value: float) -> str:
        """Format bytes in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        elif seconds < 86400:
            hours = seconds / 3600
            return f"{hours:.1f}h"
        else:
            days = seconds / 86400
            return f"{days:.1f}d"
    
    def aggregate_with(self, other: 'Metric') -> 'Metric':
        """
        Aggregate this metric with another metric.
        
        Args:
            other: Another metric to aggregate with
            
        Returns:
            Metric: New aggregated metric
            
        Raises:
            ValueError: If metrics cannot be aggregated
        """
        if (self.device_id != other.device_id or 
            self.name != other.name or 
            self.metric_type != other.metric_type):
            raise ValueError("Cannot aggregate metrics with different device_id, name, or type")
        
        # Only aggregate numeric values
        self_numeric = self.get_numeric_value()
        other_numeric = other.get_numeric_value()
        
        if self_numeric is None or other_numeric is None:
            raise ValueError("Cannot aggregate non-numeric metrics")
        
        # Calculate aggregated values
        new_sample_count = self.sample_count + other.sample_count
        new_sum = (self.sum_value or 0) + (other.sum_value or 0)
        new_min = min(self.min_value or float('inf'), other.min_value or float('inf'))
        new_max = max(self.max_value or float('-inf'), other.max_value or float('-inf'))
        new_avg = new_sum / new_sample_count
        
        # Use the latest timestamp
        new_timestamp = max(self.timestamp, other.timestamp)
        
        # Merge tags and metadata
        new_tags = {**self.tags, **other.tags}
        new_metadata = {**self.metadata, **other.metadata}
        
        return Metric(
            device_id=self.device_id,
            metric_type=self.metric_type,
            name=self.name,
            value=new_avg,
            unit=self.unit,
            timestamp=new_timestamp,
            description=self.description,
            tags=new_tags,
            metadata=new_metadata,
            quality=min(self.quality, other.quality),
            source=self.source,
            threshold=self.threshold,
            sample_count=new_sample_count,
            min_value=new_min,
            max_value=new_max,
            sum_value=new_sum
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary."""
        data = {
            'device_id': self.device_id,
            'metric_type': self.metric_type.value,
            'name': self.name,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat(),
            'description': self.description,
            'tags': self.tags,
            'metadata': self.metadata,
            'quality': self.quality,
            'source': self.source,
            'sample_count': self.sample_count,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'sum_value': self.sum_value
        }
        
        if self.threshold:
            data['threshold'] = self.threshold.to_dict()
        
        if self.severity:
            data['severity'] = self.severity.value
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Metric':
        """Create metric from dictionary."""
        # Parse datetime
        if 'timestamp' in data:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        
        # Parse enums
        if 'metric_type' in data:
            data['metric_type'] = MetricType(data['metric_type'])
        
        if 'severity' in data and data['severity']:
            data['severity'] = MetricSeverity(data['severity'])
        
        # Parse threshold
        if 'threshold' in data and data['threshold']:
            data['threshold'] = MetricThreshold(**data['threshold'])
        
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert metric to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Metric':
        """Create metric from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def to_influxdb_point(self) -> Dict[str, Any]:
        """Convert metric to InfluxDB point format."""
        point = {
            'measurement': self.name,
            'tags': {
                'device_id': self.device_id,
                'metric_type': self.metric_type.value,
                'unit': self.unit,
                **self.tags
            },
            'fields': {
                'value': self.get_numeric_value() or 0,
                'quality': self.quality,
                'sample_count': self.sample_count
            },
            'time': self.timestamp
        }
        
        # Add aggregation fields if available
        if self.min_value is not None:
            point['fields']['min_value'] = self.min_value
        if self.max_value is not None:
            point['fields']['max_value'] = self.max_value
        if self.sum_value is not None:
            point['fields']['sum_value'] = self.sum_value
        
        # Add string/boolean values as tags
        if not self.is_numeric():
            point['tags']['string_value'] = str(self.value)
        
        # Add severity if available
        if self.severity:
            point['tags']['severity'] = self.severity.value
        
        # Add source if available
        if self.source:
            point['tags']['source'] = self.source
        
        return point
    
    def to_prometheus_format(self) -> str:
        """Convert metric to Prometheus format."""
        # Sanitize metric name for Prometheus
        metric_name = self.name.replace('-', '_').replace('.', '_')
        metric_name = f"network_agent_{metric_name}"
        
        # Build labels
        labels = [
            f'device_id="{self.device_id}"',
            f'metric_type="{self.metric_type.value}"',
            f'unit="{self.unit}"'
        ]
        
        # Add tags as labels
        for key, value in self.tags.items():
            safe_key = key.replace('-', '_').replace('.', '_')
            labels.append(f'{safe_key}="{value}"')
        
        # Add severity if available
        if self.severity:
            labels.append(f'severity="{self.severity.value}"')
        
        labels_str = '{' + ','.join(labels) + '}'
        
        # Get numeric value
        numeric_value = self.get_numeric_value()
        if numeric_value is None:
            numeric_value = 1 if self.value else 0
        
        # Convert timestamp to milliseconds
        timestamp_ms = int(self.timestamp.timestamp() * 1000)
        
        return f"{metric_name}{labels_str} {numeric_value} {timestamp_ms}"
    
    def clone(self) -> 'Metric':
        """Create a copy of the metric."""
        return Metric.from_dict(self.to_dict())
    
    def __str__(self) -> str:
        """String representation of metric."""
        return f"Metric({self.device_id}.{self.name}={self.get_display_value()})"
    
    def __repr__(self) -> str:
        """Detailed string representation of metric."""
        return (f"Metric(device_id='{self.device_id}', name='{self.name}', "
                f"value={self.value}, unit='{self.unit}', "
                f"timestamp={self.timestamp.isoformat()})")
    
    def __eq__(self, other) -> bool:
        """Check equality based on device_id, name, and timestamp."""
        if not isinstance(other, Metric):
            return False
        return (self.device_id == other.device_id and 
                self.name == other.name and 
                self.timestamp == other.timestamp)
    
    def __hash__(self) -> int:
        """Hash based on device_id, name, and timestamp."""
        return hash((self.device_id, self.name, self.timestamp))
    
    def __lt__(self, other) -> bool:
        """Compare metrics by timestamp."""
        if not isinstance(other, Metric):
            return NotImplemented
        return self.timestamp < other.timestamp


class MetricCollection:
    """Collection of metrics with utility methods."""
    
    def __init__(self, metrics: List[Metric] = None):
        """Initialize metric collection."""
        self.metrics = metrics or []
    
    def add(self, metric: Metric):
        """Add a metric to the collection."""
        self.metrics.append(metric)
    
    def extend(self, metrics: List[Metric]):
        """Add multiple metrics to the collection."""
        self.metrics.extend(metrics)
    
    def filter_by_device(self, device_id: str) -> 'MetricCollection':
        """Filter metrics by device ID."""
        filtered = [m for m in self.metrics if m.device_id == device_id]
        return MetricCollection(filtered)
    
    def filter_by_type(self, metric_type: MetricType) -> 'MetricCollection':
        """Filter metrics by type."""
        filtered = [m for m in self.metrics if m.metric_type == metric_type]
        return MetricCollection(filtered)
    
    def filter_by_name(self, name: str) -> 'MetricCollection':
        """Filter metrics by name."""
        filtered = [m for m in self.metrics if m.name == name]
        return MetricCollection(filtered)
    
    def filter_by_severity(self, severity: MetricSeverity) -> 'MetricCollection':
        """Filter metrics by severity."""
        filtered = [m for m in self.metrics if m.severity == severity]
        return MetricCollection(filtered)
    
    def filter_by_time_range(self, start_time: datetime, end_time: datetime) -> 'MetricCollection':
        """Filter metrics by time range."""
        filtered = [m for m in self.metrics if start_time <= m.timestamp <= end_time]
        return MetricCollection(filtered)
    
    def get_latest(self) -> Optional[Metric]:
        """Get the latest metric by timestamp."""
        if not self.metrics:
            return None
        return max(self.metrics, key=lambda m: m.timestamp)
    
    def get_oldest(self) -> Optional[Metric]:
        """Get the oldest metric by timestamp."""
        if not self.metrics:
            return None
        return min(self.metrics, key=lambda m: m.timestamp)
    
    def sort_by_timestamp(self, reverse: bool = False) -> 'MetricCollection':
        """Sort metrics by timestamp."""
        sorted_metrics = sorted(self.metrics, key=lambda m: m.timestamp, reverse=reverse)
        return MetricCollection(sorted_metrics)
    
    def group_by_device(self) -> Dict[str, 'MetricCollection']:
        """Group metrics by device ID."""
        groups = {}
        for metric in self.metrics:
            if metric.device_id not in groups:
                groups[metric.device_id] = MetricCollection()
            groups[metric.device_id].add(metric)
        return groups
    
    def group_by_name(self) -> Dict[str, 'MetricCollection']:
        """Group metrics by name."""
        groups = {}
        for metric in self.metrics:
            if metric.name not in groups:
                groups[metric.name] = MetricCollection()
            groups[metric.name].add(metric)
        return groups
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert all metrics to list of dictionaries."""
        return [metric.to_dict() for metric in self.metrics]
    
    def to_json(self) -> str:
        """Convert all metrics to JSON string."""
        return json.dumps(self.to_dict_list(), indent=2)
    
    def __len__(self) -> int:
        """Get number of metrics in collection."""
        return len(self.metrics)
    
    def __iter__(self):
        """Iterate over metrics."""
        return iter(self.metrics)
    
    def __getitem__(self, index) -> Metric:
        """Get metric by index."""
        return self.metrics[index]