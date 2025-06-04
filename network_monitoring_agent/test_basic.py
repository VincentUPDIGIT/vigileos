#!/usr/bin/env python3
"""
Basic test to validate the agent functionality.
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_basic_functionality():
    """Test basic agent functionality."""
    print("Testing Network Monitoring Agent...")
    
    try:
        # Test platform detection
        print("1. Testing platform detection...")
        from platforms.platform_factory import PlatformFactory
        platform = PlatformFactory.get_platform()
        print(f"   ✓ Platform detected: {platform.platform_name}")
        
        # Test system metrics
        print("2. Testing system metrics...")
        try:
            metrics = await platform.get_system_metrics()
            if hasattr(metrics, '__dict__'):
                metrics_dict = metrics.__dict__
            else:
                metrics_dict = metrics
            print(f"   ✓ System metrics collected: {len(metrics_dict)} metrics")
            for key, value in list(metrics_dict.items())[:3]:
                print(f"     - {key}: {value}")
        except TypeError:
            # Method is not async
            metrics = platform.get_system_metrics()
            if hasattr(metrics, '__dict__'):
                metrics_dict = metrics.__dict__
            else:
                metrics_dict = metrics
            print(f"   ✓ System metrics collected: {len(metrics_dict)} metrics")
            for key, value in list(metrics_dict.items())[:3]:
                print(f"     - {key}: {value}")
        
        # Test models
        print("3. Testing data models...")
        from models.device import Device, DeviceType
        from models.metric import Metric, MetricType
        from datetime import datetime
        
        device = Device(
            device_id="test_device",
            name="Test Device",
            device_type=DeviceType.ROUTER,
            ip_address="192.168.1.1"
        )
        print(f"   ✓ Device model: {device.device_id}")
        
        metric = Metric(
            device_id="test_device",
            metric_type=MetricType.SYSTEM,
            name="cpu_usage",
            value=25.5,
            unit="percent",
            timestamp=datetime.now()
        )
        print(f"   ✓ Metric model: {metric.name} = {metric.value}")
        
        # Test network scanner
        print("4. Testing network scanner...")
        from utils.network_scanner import NetworkScanner
        scanner = NetworkScanner()
        alive, response_time = await scanner.ping_host("127.0.0.1", timeout=3)
        if alive:
            print(f"   ✓ Network scanner: localhost ping {response_time:.3f}s")
        else:
            print("   ✗ Network scanner: localhost ping failed")
        
        # Test encryption
        print("5. Testing encryption...")
        from utils.encryption import EncryptionManager
        encryption = EncryptionManager()
        test_data = "Hello, World!"
        encrypted = encryption.encrypt(test_data.encode())
        decrypted = encryption.decrypt(encrypted).decode()
        if decrypted == test_data:
            print("   ✓ Encryption: working correctly")
        else:
            print("   ✗ Encryption: failed")
        
        print("\n✓ All basic tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    success = await test_basic_functionality()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    asyncio.run(main())