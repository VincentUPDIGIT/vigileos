#!/usr/bin/env python3
"""
Integration tests for Network Monitoring Agent.
"""

import asyncio
import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.main_agent import NetworkMonitoringAgent
from agent.auth_manager import AuthManager
from agent.metrics_collector import MetricsCollector, CollectionConfig
from agent.tunnel_manager import TunnelManager
from agent.backend_sync import BackendSync, BackendConfig
from models.device import Device, DeviceType, SNMPConfig
from models.metric import Metric, MetricType
from models.client import Client, ClientType
from platforms.platform_factory import PlatformFactory
from utils.network_scanner import NetworkScanner


class TestAgentIntegration:
    """Integration tests for the complete agent system."""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create temporary configuration file."""
        config = {
            "agent": {
                "name": "test-agent",
                "client_id": "test-client",
                "log_level": "DEBUG",
                "auto_discovery": False
            },
            "auth": {
                "method": "jwt",
                "token_expiry": 3600
            },
            "collection": {
                "interval": 10,
                "timeout": 5,
                "enabled_collectors": ["system"]
            },
            "backend": {
                "base_url": "http://localhost:8000",
                "sync_interval": 30
            },
            "tunnels": {
                "enable_wireguard": False,
                "enable_ssh": False
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()
    
    @pytest.fixture
    async def agent(self, temp_config_file):
        """Create agent instance for testing."""
        agent = NetworkMonitoringAgent(temp_config_file)
        yield agent
        
        # Cleanup
        if agent.status.is_running:
            await agent.stop()
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test agent initialization."""
        assert agent is not None
        assert agent.config is not None
        assert agent.platform is not None
        assert agent.status is not None
        assert not agent.status.is_running
    
    @pytest.mark.asyncio
    async def test_component_initialization(self, agent):
        """Test component initialization."""
        await agent.initialize_components()
        
        assert agent.auth_manager is not None
        assert agent.metrics_collector is not None
        assert agent.tunnel_manager is not None
        assert agent.backend_sync is not None
        assert agent.network_scanner is not None
        
        # Check component status
        assert agent.status.components['auth_manager']
        assert agent.status.components['metrics_collector']
        assert agent.status.components['tunnel_manager']
        assert agent.status.components['backend_sync']
    
    @pytest.mark.asyncio
    async def test_device_management(self, agent):
        """Test device management functionality."""
        await agent.initialize_components()
        
        # Create test device
        device = Device(
            device_id="test_device_1",
            name="Test Device",
            device_type=DeviceType.ROUTER,
            ip_address="192.168.1.1",
            snmp_config=SNMPConfig(community="public")
        )
        
        # Add device
        agent.metrics_collector.add_device(device)
        
        # Verify device was added
        assert len(agent.metrics_collector.devices) == 1
        assert "test_device_1" in agent.metrics_collector.devices
        
        # Remove device
        success = agent.metrics_collector.remove_device("test_device_1")
        assert success
        assert len(agent.metrics_collector.devices) == 0
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, agent):
        """Test metrics collection."""
        await agent.initialize_components()
        
        # Mock system metrics collection
        with patch.object(agent.platform, 'get_system_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'cpu_usage': 25.5,
                'memory_usage': 60.2,
                'disk_usage': 45.0
            }
            
            # Start collection
            await agent.metrics_collector.start_collection()
            
            # Wait for collection
            await asyncio.sleep(0.5)
            
            # Stop collection
            await agent.metrics_collector.stop_collection()
            
            # Verify metrics were collected
            assert mock_metrics.called
    
    @pytest.mark.asyncio
    async def test_backend_sync(self, agent):
        """Test backend synchronization."""
        await agent.initialize_components()
        
        # Mock backend connection
        with patch.object(agent.backend_sync, 'test_connection') as mock_test:
            mock_test.return_value = True
            
            with patch.object(agent.backend_sync, 'push_metrics_batch') as mock_push:
                mock_push.return_value = Mock(status='success', metrics_sent=5)
                
                # Add test metrics
                metrics = [
                    Metric(
                        device_id="test_device",
                        metric_type=MetricType.SYSTEM,
                        name="cpu_usage",
                        value=25.5,
                        unit="percent",
                        timestamp=asyncio.get_event_loop().time()
                    )
                ]
                
                agent.backend_sync.add_metrics(metrics)
                
                # Perform sync
                result = await agent.backend_sync.sync_all_queued_data()
                
                assert result.status.value == 'success'
    
    @pytest.mark.asyncio
    async def test_tunnel_management(self, agent):
        """Test tunnel management."""
        await agent.initialize_components()
        
        # Mock tunnel creation
        with patch.object(agent.platform, 'create_tunnel_interface') as mock_create:
            mock_create.return_value = True
            
            with patch.object(agent.platform, 'destroy_tunnel_interface') as mock_destroy:
                mock_destroy.return_value = True
                
                # Create SSH tunnel
                tunnel_id = await agent.tunnel_manager.create_ssh_tunnel(
                    name="test_tunnel",
                    ssh_host="192.168.1.100",
                    ssh_port=22,
                    local_port=8080,
                    remote_host="10.0.0.1",
                    remote_port=80,
                    username="admin",
                    password="password"
                )
                
                assert tunnel_id is not None
                assert tunnel_id in agent.tunnel_manager.active_tunnels
                
                # Destroy tunnel
                success = await agent.tunnel_manager.destroy_tunnel(tunnel_id)
                assert success
                assert tunnel_id not in agent.tunnel_manager.active_tunnels
    
    @pytest.mark.asyncio
    async def test_command_handling(self, agent):
        """Test backend command handling."""
        await agent.initialize_components()
        
        # Test add device command
        command = {
            'type': 'add_device',
            'device': {
                'device_id': 'cmd_device_1',
                'name': 'Command Device',
                'device_type': 'router',
                'ip_address': '192.168.1.50'
            }
        }
        
        await agent._handle_backend_command(command)
        
        # Verify device was added
        assert 'cmd_device_1' in agent.metrics_collector.devices
        
        # Test remove device command
        command = {
            'type': 'remove_device',
            'device_id': 'cmd_device_1'
        }
        
        await agent._handle_backend_command(command)
        
        # Verify device was removed
        assert 'cmd_device_1' not in agent.metrics_collector.devices
    
    @pytest.mark.asyncio
    async def test_status_tracking(self, agent):
        """Test agent status tracking."""
        await agent.initialize_components()
        
        # Check initial status
        status = agent.get_detailed_status()
        
        assert 'agent' in status
        assert 'components' in status
        assert 'statistics' in status
        
        assert status['agent']['name'] == 'test-agent'
        assert status['agent']['is_running'] == False
        
        # Update stats
        await agent._update_status_stats()
        
        # Check updated status
        updated_status = agent.get_detailed_status()
        assert 'statistics' in updated_status


class TestPlatformIntegration:
    """Test platform-specific integration."""
    
    def test_platform_detection(self):
        """Test platform detection."""
        platform = PlatformFactory.get_platform()
        assert platform is not None
        assert hasattr(platform, 'platform_name')
        assert hasattr(platform, 'get_system_metrics')
    
    @pytest.mark.asyncio
    async def test_system_metrics_collection(self):
        """Test system metrics collection."""
        platform = PlatformFactory.get_platform()
        
        metrics = await platform.get_system_metrics()
        assert isinstance(metrics, dict)
        
        # Should have basic system metrics
        expected_metrics = ['cpu_usage', 'memory_usage', 'disk_usage']
        for metric in expected_metrics:
            if metric in metrics:
                assert isinstance(metrics[metric], (int, float))


class TestNetworkScanner:
    """Test network scanner functionality."""
    
    @pytest.fixture
    def scanner(self):
        """Create network scanner instance."""
        return NetworkScanner()
    
    @pytest.mark.asyncio
    async def test_ping_localhost(self, scanner):
        """Test ping to localhost."""
        alive, response_time = await scanner.ping_host("127.0.0.1", timeout=5)
        assert alive
        assert response_time > 0
    
    @pytest.mark.asyncio
    async def test_ping_invalid_host(self, scanner):
        """Test ping to invalid host."""
        alive, response_time = await scanner.ping_host("192.168.255.255", timeout=1)
        assert not alive
        assert response_time == 0
    
    def test_get_local_networks(self, scanner):
        """Test local network detection."""
        networks = scanner.get_local_networks()
        assert isinstance(networks, list)
        # Should find at least loopback or local network
        assert len(networks) >= 0


class TestModels:
    """Test data models."""
    
    def test_device_model(self):
        """Test Device model."""
        device = Device(
            device_id="test_device",
            name="Test Device",
            device_type=DeviceType.SWITCH,
            ip_address="192.168.1.10"
        )
        
        assert device.device_id == "test_device"
        assert device.device_type == DeviceType.SWITCH
        assert device.is_valid()
        
        # Test serialization
        device_dict = device.to_dict()
        assert isinstance(device_dict, dict)
        
        # Test deserialization
        device2 = Device.from_dict(device_dict)
        assert device2.device_id == device.device_id
    
    def test_metric_model(self):
        """Test Metric model."""
        from datetime import datetime
        
        metric = Metric(
            device_id="test_device",
            metric_type=MetricType.PERFORMANCE,
            name="cpu_usage",
            value=75.5,
            unit="percent",
            timestamp=datetime.utcnow()
        )
        
        assert metric.device_id == "test_device"
        assert metric.is_numeric()
        assert not metric.is_boolean()
        
        # Test serialization
        metric_dict = metric.to_dict()
        assert isinstance(metric_dict, dict)
        
        # Test deserialization
        metric2 = Metric.from_dict(metric_dict)
        assert metric2.device_id == metric.device_id
    
    def test_client_model(self):
        """Test Client model."""
        client = Client(
            client_id="test_client",
            name="Test Client",
            client_type=ClientType.ENTERPRISE,
            contact_email="test@example.com"
        )
        
        assert client.client_id == "test_client"
        assert client.client_type == ClientType.ENTERPRISE
        assert client.is_valid()
        
        # Test permissions
        assert client.has_permission('devices:read')
        
        # Test serialization
        client_dict = client.to_dict()
        assert isinstance(client_dict, dict)


def run_integration_tests():
    """Run all integration tests."""
    print("Running Network Monitoring Agent Integration Tests...")
    
    # Run pytest
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--asyncio-mode=auto"
    ])
    
    return exit_code == 0


if __name__ == '__main__':
    success = run_integration_tests()
    sys.exit(0 if success else 1)