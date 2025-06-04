#!/usr/bin/env python3
"""
Comprehensive test runner for Network Monitoring Agent.
"""

import os
import sys
import subprocess
import asyncio
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
import time
import platform


class TestRunner:
    """Comprehensive test runner for the agent."""
    
    def __init__(self):
        """Initialize test runner."""
        self.project_root = Path(__file__).parent.parent
        self.test_results: List[Dict[str, Any]] = []
        self.start_time = time.time()
        
    def log_result(self, test_name: str, success: bool, message: str = "", duration: float = 0):
        """Log test result."""
        result = {
            'test_name': test_name,
            'success': success,
            'message': message,
            'duration': duration,
            'timestamp': time.time()
        }
        self.test_results.append(result)
        
        status = "✓" if success else "✗"
        duration_str = f" ({duration:.2f}s)" if duration > 0 else ""
        print(f"{status} {test_name}{duration_str}: {message}")
        
        return result
    
    def run_unit_tests(self) -> bool:
        """Run unit tests using pytest."""
        print("\n=== Running Unit Tests ===")
        
        start_time = time.time()
        
        try:
            # Check if pytest is available
            result = subprocess.run([sys.executable, "-m", "pytest", "--version"], 
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                self.log_result("Pytest availability", False, "pytest not installed")
                return False
            
            # Run tests
            test_dir = self.project_root / "tests"
            if not test_dir.exists():
                self.log_result("Unit tests", False, "Test directory not found")
                return False
            
            cmd = [
                sys.executable, "-m", "pytest",
                str(test_dir),
                "-v",
                "--tb=short",
                "--asyncio-mode=auto",
                "--disable-warnings"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
            duration = time.time() - start_time
            
            if result.returncode == 0:
                self.log_result("Unit tests", True, "All tests passed", duration)
                return True
            else:
                self.log_result("Unit tests", False, f"Tests failed: {result.stderr}", duration)
                print(f"STDOUT:\n{result.stdout}")
                print(f"STDERR:\n{result.stderr}")
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Unit tests", False, f"Exception: {e}", duration)
            return False
    
    def test_imports(self) -> bool:
        """Test that all modules can be imported."""
        print("\n=== Testing Module Imports ===")
        
        # Add src to path
        sys.path.insert(0, str(self.project_root / "src"))
        
        modules_to_test = [
            "agent.main_agent",
            "agent.auth_manager",
            "agent.metrics_collector",
            "agent.tunnel_manager",
            "agent.backend_sync",
            "models.device",
            "models.metric",
            "models.client",
            "platforms.platform_factory",
            "utils.logger",
            "utils.encryption",
            "utils.platform_utils",
            "utils.network_scanner",
            "apis.snmp_client",
            "apis.ssh_client",
            "apis.web_scraper",
            "apis.rest_api_client"
        ]
        
        all_success = True
        
        for module_name in modules_to_test:
            start_time = time.time()
            try:
                __import__(module_name)
                duration = time.time() - start_time
                self.log_result(f"Import {module_name}", True, "Success", duration)
            except Exception as e:
                duration = time.time() - start_time
                self.log_result(f"Import {module_name}", False, str(e), duration)
                all_success = False
        
        return all_success
    
    def test_platform_detection(self) -> bool:
        """Test platform detection."""
        print("\n=== Testing Platform Detection ===")
        
        start_time = time.time()
        
        try:
            from platforms.platform_factory import PlatformFactory
            
            platform = PlatformFactory.get_platform()
            duration = time.time() - start_time
            
            if platform:
                self.log_result("Platform detection", True, 
                              f"Detected {platform.platform_name}", duration)
                return True
            else:
                self.log_result("Platform detection", False, 
                              "Failed to detect platform", duration)
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Platform detection", False, str(e), duration)
            return False
    
    async def test_network_scanner(self) -> bool:
        """Test network scanner functionality."""
        print("\n=== Testing Network Scanner ===")
        
        start_time = time.time()
        
        try:
            from utils.network_scanner import NetworkScanner
            
            scanner = NetworkScanner()
            
            # Test ping to localhost
            alive, response_time = await scanner.ping_host("127.0.0.1", timeout=5)
            
            duration = time.time() - start_time
            
            if alive:
                self.log_result("Network scanner ping", True, 
                              f"Localhost ping: {response_time:.3f}s", duration)
                return True
            else:
                self.log_result("Network scanner ping", False, 
                              "Failed to ping localhost", duration)
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Network scanner", False, str(e), duration)
            return False
    
    async def test_agent_creation(self) -> bool:
        """Test agent creation and initialization."""
        print("\n=== Testing Agent Creation ===")
        
        start_time = time.time()
        
        try:
            from agent.main_agent import NetworkMonitoringAgent
            
            # Create temporary config
            config = {
                "agent": {
                    "name": "test-agent",
                    "client_id": "test-client",
                    "auto_discovery": False
                },
                "auth": {"method": "jwt"},
                "collection": {"interval": 60, "enabled_collectors": ["system"]},
                "backend": {"base_url": "http://localhost:8000"},
                "tunnels": {"enable_wireguard": False, "enable_ssh": False}
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(config, f)
                config_file = Path(f.name)
            
            try:
                # Create agent
                agent = NetworkMonitoringAgent(config_file)
                
                # Initialize components
                await agent.initialize_components()
                
                duration = time.time() - start_time
                self.log_result("Agent creation", True, 
                              "Agent created and initialized", duration)
                
                # Cleanup
                await agent.stop()
                return True
                
            finally:
                config_file.unlink()
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Agent creation", False, str(e), duration)
            return False
    
    def test_configuration_validation(self) -> bool:
        """Test configuration validation."""
        print("\n=== Testing Configuration Validation ===")
        
        start_time = time.time()
        
        try:
            # Test valid configuration
            valid_config = {
                "agent": {
                    "name": "test-agent",
                    "client_id": "test-client"
                },
                "auth": {"method": "jwt"},
                "collection": {"interval": 60},
                "backend": {"base_url": "http://localhost:8000"},
                "tunnels": {}
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(valid_config, f)
                config_file = Path(f.name)
            
            try:
                from agent.main_agent import NetworkMonitoringAgent
                agent = NetworkMonitoringAgent(config_file)
                
                if agent.config:
                    duration = time.time() - start_time
                    self.log_result("Configuration validation", True, 
                                  "Valid configuration loaded", duration)
                    return True
                else:
                    duration = time.time() - start_time
                    self.log_result("Configuration validation", False, 
                                  "Configuration not loaded", duration)
                    return False
                    
            finally:
                config_file.unlink()
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Configuration validation", False, str(e), duration)
            return False
    
    def test_model_serialization(self) -> bool:
        """Test model serialization/deserialization."""
        print("\n=== Testing Model Serialization ===")
        
        start_time = time.time()
        
        try:
            from models.device import Device, DeviceType
            from models.metric import Metric, MetricType
            from models.client import Client, ClientType
            from datetime import datetime
            
            # Test Device model
            device = Device(
                device_id="test_device",
                name="Test Device",
                device_type=DeviceType.ROUTER,
                ip_address="192.168.1.1"
            )
            
            device_dict = device.to_dict()
            device2 = Device.from_dict(device_dict)
            
            if device.device_id != device2.device_id:
                raise ValueError("Device serialization failed")
            
            # Test Metric model
            metric = Metric(
                device_id="test_device",
                metric_type=MetricType.PERFORMANCE,
                name="cpu_usage",
                value=75.5,
                unit="percent",
                timestamp=datetime.utcnow()
            )
            
            metric_dict = metric.to_dict()
            metric2 = Metric.from_dict(metric_dict)
            
            if metric.device_id != metric2.device_id:
                raise ValueError("Metric serialization failed")
            
            # Test Client model
            client = Client(
                client_id="test_client",
                name="Test Client",
                client_type=ClientType.ENTERPRISE,
                contact_email="test@example.com"
            )
            
            client_dict = client.to_dict()
            client2 = Client.from_dict(client_dict)
            
            if client.client_id != client2.client_id:
                raise ValueError("Client serialization failed")
            
            duration = time.time() - start_time
            self.log_result("Model serialization", True, 
                          "All models serialize correctly", duration)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Model serialization", False, str(e), duration)
            return False
    
    def test_encryption(self) -> bool:
        """Test encryption functionality."""
        print("\n=== Testing Encryption ===")
        
        start_time = time.time()
        
        try:
            from utils.encryption import EncryptionManager
            
            manager = EncryptionManager()
            
            # Test data encryption
            test_data = "This is test data for encryption"
            encrypted = manager.encrypt(test_data.encode())
            decrypted = manager.decrypt(encrypted)
            
            if decrypted.decode() != test_data:
                raise ValueError("Encryption/decryption failed")
            
            duration = time.time() - start_time
            self.log_result("Encryption", True, 
                          "Encryption/decryption working", duration)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Encryption", False, str(e), duration)
            return False
    
    def test_dependencies(self) -> bool:
        """Test that all required dependencies are available."""
        print("\n=== Testing Dependencies ===")
        
        # Core dependencies
        core_deps = [
            "asyncio",
            "json",
            "pathlib",
            "logging",
            "datetime",
            "typing"
        ]
        
        # Optional dependencies
        optional_deps = [
            ("aiohttp", "HTTP client functionality"),
            ("cryptography", "Encryption functionality"),
            ("psutil", "System metrics"),
            ("structlog", "Structured logging"),
            ("pyyaml", "YAML configuration")
        ]
        
        all_success = True
        
        # Test core dependencies
        for dep in core_deps:
            start_time = time.time()
            try:
                __import__(dep)
                duration = time.time() - start_time
                self.log_result(f"Dependency {dep}", True, "Available", duration)
            except ImportError:
                duration = time.time() - start_time
                self.log_result(f"Dependency {dep}", False, "Missing", duration)
                all_success = False
        
        # Test optional dependencies
        for dep, description in optional_deps:
            start_time = time.time()
            try:
                __import__(dep)
                duration = time.time() - start_time
                self.log_result(f"Optional {dep}", True, f"Available - {description}", duration)
            except ImportError:
                duration = time.time() - start_time
                self.log_result(f"Optional {dep}", False, f"Missing - {description}", duration)
                # Don't fail for optional dependencies
        
        return all_success
    
    async def run_all_tests(self) -> bool:
        """Run all tests."""
        print("Network Monitoring Agent Test Suite")
        print("=" * 50)
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version}")
        print(f"Project root: {self.project_root}")
        print()
        
        test_functions = [
            ("Dependencies", self.test_dependencies),
            ("Module Imports", self.test_imports),
            ("Platform Detection", self.test_platform_detection),
            ("Configuration", self.test_configuration_validation),
            ("Model Serialization", self.test_model_serialization),
            ("Encryption", self.test_encryption),
            ("Network Scanner", self.test_network_scanner),
            ("Agent Creation", self.test_agent_creation),
            ("Unit Tests", self.run_unit_tests)
        ]
        
        all_passed = True
        
        for test_name, test_func in test_functions:
            try:
                print(f"\n--- {test_name} ---")
                
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                
                if not result:
                    all_passed = False
                    
            except Exception as e:
                self.log_result(test_name, False, f"Exception: {e}")
                all_passed = False
        
        # Print summary
        self.print_summary()
        
        return all_passed
    
    def print_summary(self):
        """Print test summary."""
        total_time = time.time() - self.start_time
        
        print("\n" + "=" * 50)
        print("TEST SUMMARY")
        print("=" * 50)
        
        passed = len([r for r in self.test_results if r['success']])
        total = len(self.test_results)
        
        print(f"Total tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success rate: {(passed/total)*100:.1f}%")
        print(f"Total time: {total_time:.2f}s")
        
        if passed == total:
            print("\n✓ All tests passed! The agent appears to be working correctly.")
        else:
            print("\n✗ Some tests failed. Please check the issues above.")
            
            # Show failed tests
            failed_tests = [r for r in self.test_results if not r['success']]
            if failed_tests:
                print("\nFailed tests:")
                for test in failed_tests:
                    print(f"  - {test['test_name']}: {test['message']}")
    
    def save_report(self, report_file: Path):
        """Save test report to file."""
        report = {
            'timestamp': time.time(),
            'platform': {
                'system': platform.system(),
                'release': platform.release(),
                'machine': platform.machine(),
                'python_version': sys.version
            },
            'project_root': str(self.project_root),
            'results': self.test_results,
            'summary': {
                'total_tests': len(self.test_results),
                'passed': len([r for r in self.test_results if r['success']]),
                'failed': len([r for r in self.test_results if not r['success']]),
                'success_rate': (len([r for r in self.test_results if r['success']]) / len(self.test_results)) * 100 if self.test_results else 0,
                'total_time': time.time() - self.start_time
            }
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nTest report saved to {report_file}")


async def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Network Monitoring Agent Test Runner')
    parser.add_argument('--report', type=Path, help='Save test report to file')
    parser.add_argument('--quick', action='store_true', help='Skip unit tests for faster execution')
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    try:
        success = await runner.run_all_tests()
        
        # Save report if requested
        if args.report:
            runner.save_report(args.report)
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nTests cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest execution failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())