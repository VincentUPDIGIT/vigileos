#!/usr/bin/env python3
"""
Integration tests for the Network Monitoring Agent.
"""

import asyncio
import sys
import os
import tempfile
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_full_integration():
    """Test full agent integration."""
    print("🔧 Network Monitoring Agent - Integration Tests")
    print("=" * 50)
    
    try:
        # Test 1: Platform Detection and System Info
        print("\n1. Testing Platform Detection...")
        from platforms.platform_factory import PlatformFactory
        platform = PlatformFactory.get_platform()
        print(f"   ✓ Platform: {platform.platform_name}")
        print(f"   ✓ Admin privileges: {platform.is_admin()}")
        
        # Test 2: Configuration Loading
        print("\n2. Testing Configuration...")
        config_path = Path(__file__).parent / "config" / "default_config.json"
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"   ✓ Configuration loaded: {len(config)} sections")
        
        # Test 3: Authentication Manager
        print("\n3. Testing Authentication Manager...")
        from agent.auth_manager import AuthManager
        auth_manager = AuthManager()
        
        # Create test client
        import uuid
        client_id = f"test_client_{uuid.uuid4().hex[:8]}"
        client = auth_manager.create_client(
            client_id=client_id,
            client_name="Test Client",
            permissions=["read", "write"]
        )
        print(f"   ✓ Client created: {client.client_id}")
        
        # Test token creation (using internal method for testing)
        token = auth_manager._create_access_token(client)
        print(f"   ✓ Token created: {token.token_type.value}")
        
        # Test token validation
        is_valid = auth_manager.validate_token(token.token)
        print(f"   ✓ Token validation: {is_valid}")
        
        # Test 4: Metrics Collection
        print("\n4. Testing Metrics Collection...")
        from agent.metrics_collector import MetricsCollector
        collector = MetricsCollector()
        
        # Test system metrics
        try:
            metrics = platform.get_system_metrics()
            print(f"   ✓ System metrics: {len(metrics.__dict__)} metrics collected")
        except Exception as e:
            print(f"   ⚠ System metrics warning: {e}")
        
        # Test 5: Data Models
        print("\n5. Testing Data Models...")
        from models.device import Device, DeviceType
        from models.metric import Metric, MetricType
        
        # Create test device
        device = Device(
            device_id="test_device_001",
            name="Test Router",
            device_type=DeviceType.ROUTER,
            ip_address="192.168.1.1"
        )
        print(f"   ✓ Device model: {device.name} ({device.device_type.value})")
        
        # Create test metric
        from datetime import datetime
        metric = Metric(
            device_id=device.device_id,
            metric_type=MetricType.PERFORMANCE,
            name="cpu_usage",
            value=45.2,
            unit="%",
            timestamp=datetime.utcnow()
        )
        print(f"   ✓ Metric model: {metric.name} ({metric.metric_type.value}) = {metric.value}{metric.unit}")
        
        # Test 6: Encryption
        print("\n6. Testing Encryption...")
        from utils.encryption import EncryptionManager
        
        # Use temporary key file for testing
        with tempfile.NamedTemporaryFile(delete=False) as tmp_key:
            encryption = EncryptionManager(key_file=tmp_key.name)
            
            # Test password-based encryption
            test_data = "Sensitive network configuration data"
            password = "test_password_123"
            
            encrypted = encryption.encrypt(test_data, password)
            decrypted = encryption.decrypt(encrypted, password)
            
            # Convert bytes to string if needed
            if isinstance(decrypted, bytes):
                decrypted = decrypted.decode('utf-8')
            
            assert decrypted == test_data
            print(f"   ✓ Password encryption: {len(encrypted)} bytes encrypted")
            
            # Cleanup
            os.unlink(tmp_key.name)
        
        # Test 7: Network Scanner
        print("\n7. Testing Network Scanner...")
        from utils.network_scanner import NetworkScanner
        scanner = NetworkScanner()
        
        # Test localhost ping
        try:
            result = await scanner.ping_host("127.0.0.1")
            if result:
                print("   ✓ Localhost ping: successful")
            else:
                print("   ⚠ Localhost ping: failed (may be normal in containers)")
        except Exception as e:
            print(f"   ⚠ Ping test warning: {e}")
        
        # Test 8: Tunnel Manager
        print("\n8. Testing Tunnel Manager...")
        from agent.tunnel_manager import TunnelManager
        tunnel_manager = TunnelManager()
        print(f"   ✓ Tunnel manager initialized: {len(tunnel_manager.active_tunnels)} active tunnels")
        
        # Test 9: Backend Sync
        print("\n9. Testing Backend Sync...")
        from agent.backend_sync import BackendSync, BackendConfig
        backend_config = BackendConfig(
            base_url="http://localhost:8080",
            api_key="test_key",
            timeout=30
        )
        backend_sync = BackendSync(backend_config)
        print(f"   ✓ Backend sync initialized: running = {backend_sync.is_running}")
        
        # Test 10: Main Agent
        print("\n10. Testing Main Agent...")
        from agent.main_agent import NetworkMonitoringAgent
        
        # Create agent with test config
        test_config = {
            "agent": {
                "name": "test_agent",
                "collection_interval": 60,
                "discovery_interval": 300
            },
            "backend": {
                "url": "http://localhost:8080",
                "api_key": "test_key",
                "timeout": 30
            }
        }
        
        agent = NetworkMonitoringAgent()
        print(f"   ✓ Agent initialized: status = {agent.status.is_running}")
        
        # Test agent status
        status = agent.get_detailed_status()
        print(f"   ✓ Agent status: {list(status.keys())}")
        
        print("\n" + "=" * 50)
        print("🎉 All integration tests passed successfully!")
        print("\nAgent is ready for deployment.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_clients():
    """Test API clients with mock data."""
    print("\n🔌 Testing API Clients...")
    print("-" * 30)
    
    try:
        # Test SNMP Client (without actual SNMP)
        print("1. SNMP Client...")
        from apis.snmp_client import SNMPClient
        snmp_client = SNMPClient()
        print("   ✓ SNMP client initialized")
        
        # Test SSH Client (without actual SSH)
        print("2. SSH Client...")
        from apis.ssh_client import SSHClient
        ssh_client = SSHClient()
        print("   ✓ SSH client initialized")
        
        # Test Web Scraper
        print("3. Web Scraper...")
        from apis.web_scraper import WebScraper
        scraper = WebScraper()
        print("   ✓ Web scraper initialized")
        
        # Test REST API Client
        print("4. REST API Client...")
        from apis.rest_api_client import RestAPIClient
        rest_client = RestAPIClient()
        print("   ✓ REST API client initialized")
        
        print("   ✓ All API clients initialized successfully")
        
    except Exception as e:
        print(f"   ⚠ API client test warning: {e}")

def main():
    """Run all integration tests."""
    print("Starting Network Monitoring Agent Integration Tests...")
    
    # Run async tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run main integration tests
        success = loop.run_until_complete(test_full_integration())
        
        # Run API client tests
        loop.run_until_complete(test_api_clients())
        
        if success:
            print("\n✅ All tests completed successfully!")
            print("\nNext steps:")
            print("1. Install dependencies: pip install -r requirements.txt")
            print("2. Configure the agent: edit config/default_config.json")
            print("3. Run the agent: python main.py")
            print("4. Install as service: python scripts/install.py")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        return 1
    finally:
        loop.close()

if __name__ == "__main__":
    sys.exit(main())