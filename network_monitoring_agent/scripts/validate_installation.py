#!/usr/bin/env python3
"""
Installation validation script for Network Monitoring Agent.
"""

import os
import sys
import subprocess
import platform
import json
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any
import importlib.util


class ValidationResult:
    """Validation result container."""
    
    def __init__(self, name: str, success: bool, message: str = "", details: Any = None):
        self.name = name
        self.success = success
        self.message = message
        self.details = details
        self.timestamp = time.time()


class AgentValidator:
    """Network Monitoring Agent installation validator."""
    
    def __init__(self):
        """Initialize validator."""
        self.system = platform.system().lower()
        self.results: List[ValidationResult] = []
        self.install_locations = self._get_install_locations()
        
    def _get_install_locations(self) -> Dict[str, Path]:
        """Get expected installation locations."""
        if self.system == "linux":
            return {
                'base': Path('/opt/network-agent'),
                'config': Path('/etc/network-agent'),
                'data': Path('/var/lib/network-agent'),
                'logs': Path('/var/log/network-agent'),
                'bin': Path('/usr/local/bin')
            }
        elif self.system == "darwin":  # macOS
            return {
                'base': Path('/opt/network-agent'),
                'config': Path('/etc/network-agent'),
                'data': Path('/var/lib/network-agent'),
                'logs': Path('/var/log/network-agent'),
                'bin': Path('/usr/local/bin')
            }
        elif self.system == "windows":
            program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
            program_data = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
            return {
                'base': Path(program_files) / 'NetworkAgent',
                'config': Path(program_data) / 'NetworkAgent',
                'data': Path(program_data) / 'NetworkAgent' / 'data',
                'logs': Path(program_data) / 'NetworkAgent' / 'logs',
                'bin': Path(program_files) / 'NetworkAgent' / 'bin'
            }
        else:
            return {}
    
    def add_result(self, name: str, success: bool, message: str = "", details: Any = None):
        """Add validation result."""
        result = ValidationResult(name, success, message, details)
        self.results.append(result)
        
        status = "✓" if success else "✗"
        print(f"{status} {name}: {message}")
        
        return result
    
    def validate_directories(self) -> bool:
        """Validate installation directories."""
        print("\n=== Directory Validation ===")
        
        all_valid = True
        
        for name, path in self.install_locations.items():
            if path.exists() and path.is_dir():
                self.add_result(f"Directory {name}", True, f"Exists at {path}")
            else:
                self.add_result(f"Directory {name}", False, f"Missing at {path}")
                all_valid = False
        
        return all_valid
    
    def validate_files(self) -> bool:
        """Validate installation files."""
        print("\n=== File Validation ===")
        
        all_valid = True
        base_dir = self.install_locations['base']
        
        # Required files
        required_files = [
            'src/agent/main_agent.py',
            'src/agent/auth_manager.py',
            'src/agent/metrics_collector.py',
            'src/agent/tunnel_manager.py',
            'src/agent/backend_sync.py',
            'requirements.txt',
            'VERSION'
        ]
        
        for file_path in required_files:
            full_path = base_dir / file_path
            if full_path.exists():
                self.add_result(f"File {file_path}", True, "Exists")
            else:
                self.add_result(f"File {file_path}", False, "Missing")
                all_valid = False
        
        # Configuration file
        config_file = self.install_locations['config'] / 'config.json'
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                self.add_result("Configuration file", True, "Valid JSON")
            except Exception as e:
                self.add_result("Configuration file", False, f"Invalid JSON: {e}")
                all_valid = False
        else:
            self.add_result("Configuration file", False, "Missing")
            all_valid = False
        
        return all_valid
    
    def validate_permissions(self) -> bool:
        """Validate file permissions."""
        print("\n=== Permission Validation ===")
        
        all_valid = True
        
        if self.system in ["linux", "darwin"]:
            # Check executable permissions
            bin_file = self.install_locations['bin'] / 'network-agent'
            if bin_file.exists():
                if os.access(bin_file, os.X_OK):
                    self.add_result("Binary executable", True, "Has execute permission")
                else:
                    self.add_result("Binary executable", False, "Missing execute permission")
                    all_valid = False
            
            # Check directory permissions
            for name, path in self.install_locations.items():
                if path.exists():
                    if os.access(path, os.R_OK):
                        self.add_result(f"Directory {name} readable", True, "Has read permission")
                    else:
                        self.add_result(f"Directory {name} readable", False, "Missing read permission")
                        all_valid = False
        
        return all_valid
    
    def validate_dependencies(self) -> bool:
        """Validate Python dependencies."""
        print("\n=== Dependency Validation ===")
        
        all_valid = True
        base_dir = self.install_locations['base']
        requirements_file = base_dir / 'requirements.txt'
        
        if not requirements_file.exists():
            self.add_result("Requirements file", False, "Missing requirements.txt")
            return False
        
        try:
            with open(requirements_file, 'r') as f:
                requirements = f.read().strip().split('\n')
            
            for requirement in requirements:
                if not requirement.strip() or requirement.startswith('#'):
                    continue
                
                # Extract package name
                package_name = requirement.split('==')[0].split('>=')[0].split('<=')[0].strip()
                
                try:
                    importlib.import_module(package_name.replace('-', '_'))
                    self.add_result(f"Package {package_name}", True, "Installed")
                except ImportError:
                    self.add_result(f"Package {package_name}", False, "Not installed")
                    all_valid = False
        
        except Exception as e:
            self.add_result("Dependency check", False, f"Error reading requirements: {e}")
            all_valid = False
        
        return all_valid
    
    def validate_service(self) -> bool:
        """Validate system service."""
        print("\n=== Service Validation ===")
        
        all_valid = True
        
        try:
            if self.system == "linux":
                # Check systemd service
                result = subprocess.run(
                    ['systemctl', 'status', 'network-monitoring-agent'],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    self.add_result("Systemd service", True, "Service exists")
                    
                    # Check if enabled
                    enabled_result = subprocess.run(
                        ['systemctl', 'is-enabled', 'network-monitoring-agent'],
                        capture_output=True, text=True
                    )
                    
                    if enabled_result.stdout.strip() == 'enabled':
                        self.add_result("Service enabled", True, "Service is enabled")
                    else:
                        self.add_result("Service enabled", False, "Service is not enabled")
                        all_valid = False
                else:
                    self.add_result("Systemd service", False, "Service not found")
                    all_valid = False
            
            elif self.system == "darwin":
                # Check launchd service
                result = subprocess.run(
                    ['launchctl', 'list', 'com.company.network-monitoring-agent'],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    self.add_result("Launchd service", True, "Service exists")
                else:
                    self.add_result("Launchd service", False, "Service not found")
                    all_valid = False
            
            elif self.system == "windows":
                # Check Windows service
                result = subprocess.run(
                    ['sc', 'query', 'NetworkMonitoringAgent'],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    self.add_result("Windows service", True, "Service exists")
                else:
                    self.add_result("Windows service", False, "Service not found")
                    all_valid = False
        
        except Exception as e:
            self.add_result("Service validation", False, f"Error checking service: {e}")
            all_valid = False
        
        return all_valid
    
    def validate_network_connectivity(self) -> bool:
        """Validate network connectivity."""
        print("\n=== Network Connectivity Validation ===")
        
        all_valid = True
        
        # Test basic connectivity
        test_hosts = ["8.8.8.8", "1.1.1.1"]
        
        for host in test_hosts:
            try:
                if self.system == "windows":
                    cmd = ["ping", "-n", "1", "-w", "3000", host]
                else:
                    cmd = ["ping", "-c", "1", "-W", "3", host]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    self.add_result(f"Ping {host}", True, "Reachable")
                else:
                    self.add_result(f"Ping {host}", False, "Unreachable")
                    all_valid = False
            
            except Exception as e:
                self.add_result(f"Ping {host}", False, f"Error: {e}")
                all_valid = False
        
        return all_valid
    
    async def validate_agent_functionality(self) -> bool:
        """Validate agent functionality."""
        print("\n=== Agent Functionality Validation ===")
        
        all_valid = True
        base_dir = self.install_locations['base']
        
        # Add base directory to Python path
        sys.path.insert(0, str(base_dir))
        
        try:
            # Test imports
            from src.agent.main_agent import NetworkMonitoringAgent
            from src.platforms.platform_factory import PlatformFactory
            from src.utils.network_scanner import NetworkScanner
            
            self.add_result("Module imports", True, "All modules importable")
            
            # Test platform detection
            platform = PlatformFactory.get_platform()
            if platform:
                self.add_result("Platform detection", True, f"Detected {platform.platform_name}")
            else:
                self.add_result("Platform detection", False, "Failed to detect platform")
                all_valid = False
            
            # Test network scanner
            scanner = NetworkScanner()
            alive, response_time = await scanner.ping_host("127.0.0.1", timeout=3)
            
            if alive:
                self.add_result("Network scanner", True, f"Localhost ping: {response_time:.3f}s")
            else:
                self.add_result("Network scanner", False, "Failed to ping localhost")
                all_valid = False
            
            # Test agent creation (without starting)
            config_file = self.install_locations['config'] / 'config.json'
            if config_file.exists():
                agent = NetworkMonitoringAgent(config_file)
                if agent:
                    self.add_result("Agent creation", True, "Agent instance created")
                else:
                    self.add_result("Agent creation", False, "Failed to create agent")
                    all_valid = False
            
        except Exception as e:
            self.add_result("Agent functionality", False, f"Error: {e}")
            all_valid = False
        
        return all_valid
    
    def validate_configuration(self) -> bool:
        """Validate configuration."""
        print("\n=== Configuration Validation ===")
        
        all_valid = True
        config_file = self.install_locations['config'] / 'config.json'
        
        if not config_file.exists():
            self.add_result("Configuration file", False, "Missing")
            return False
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Check required sections
            required_sections = ['agent', 'auth', 'collection', 'backend', 'tunnels']
            
            for section in required_sections:
                if section in config:
                    self.add_result(f"Config section {section}", True, "Present")
                else:
                    self.add_result(f"Config section {section}", False, "Missing")
                    all_valid = False
            
            # Validate specific settings
            if 'agent' in config:
                agent_config = config['agent']
                
                if 'client_id' in agent_config and agent_config['client_id']:
                    self.add_result("Client ID", True, f"Set to {agent_config['client_id']}")
                else:
                    self.add_result("Client ID", False, "Not configured")
                    all_valid = False
                
                if 'data_dir' in agent_config:
                    data_dir = Path(agent_config['data_dir'])
                    if data_dir.exists():
                        self.add_result("Data directory", True, f"Exists at {data_dir}")
                    else:
                        self.add_result("Data directory", False, f"Missing at {data_dir}")
                        all_valid = False
        
        except Exception as e:
            self.add_result("Configuration validation", False, f"Error: {e}")
            all_valid = False
        
        return all_valid
    
    def validate_logs(self) -> bool:
        """Validate logging setup."""
        print("\n=== Logging Validation ===")
        
        all_valid = True
        log_dir = self.install_locations['logs']
        
        if log_dir.exists():
            self.add_result("Log directory", True, f"Exists at {log_dir}")
            
            # Check if writable
            test_file = log_dir / 'test_write.tmp'
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                test_file.unlink()
                self.add_result("Log directory writable", True, "Can write to log directory")
            except Exception as e:
                self.add_result("Log directory writable", False, f"Cannot write: {e}")
                all_valid = False
        else:
            self.add_result("Log directory", False, "Missing")
            all_valid = False
        
        return all_valid
    
    async def run_full_validation(self) -> bool:
        """Run complete validation suite."""
        print("Network Monitoring Agent Installation Validation")
        print("=" * 50)
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version}")
        print()
        
        validation_steps = [
            ("Directories", self.validate_directories),
            ("Files", self.validate_files),
            ("Permissions", self.validate_permissions),
            ("Dependencies", self.validate_dependencies),
            ("Service", self.validate_service),
            ("Configuration", self.validate_configuration),
            ("Logging", self.validate_logs),
            ("Network", self.validate_network_connectivity),
            ("Functionality", self.validate_agent_functionality)
        ]
        
        all_passed = True
        
        for step_name, step_func in validation_steps:
            try:
                if asyncio.iscoroutinefunction(step_func):
                    result = await step_func()
                else:
                    result = step_func()
                
                if not result:
                    all_passed = False
            
            except Exception as e:
                self.add_result(f"{step_name} validation", False, f"Exception: {e}")
                all_passed = False
        
        # Summary
        print("\n" + "=" * 50)
        print("VALIDATION SUMMARY")
        print("=" * 50)
        
        passed = len([r for r in self.results if r.success])
        total = len(self.results)
        
        print(f"Total checks: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success rate: {(passed/total)*100:.1f}%")
        
        if all_passed:
            print("\n✓ All validations passed! Installation appears to be successful.")
        else:
            print("\n✗ Some validations failed. Please check the issues above.")
            
            # Show failed checks
            failed_checks = [r for r in self.results if not r.success]
            if failed_checks:
                print("\nFailed checks:")
                for check in failed_checks:
                    print(f"  - {check.name}: {check.message}")
        
        return all_passed
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate validation report."""
        return {
            'timestamp': time.time(),
            'platform': {
                'system': platform.system(),
                'release': platform.release(),
                'machine': platform.machine(),
                'python_version': sys.version
            },
            'install_locations': {k: str(v) for k, v in self.install_locations.items()},
            'results': [
                {
                    'name': r.name,
                    'success': r.success,
                    'message': r.message,
                    'timestamp': r.timestamp
                }
                for r in self.results
            ],
            'summary': {
                'total_checks': len(self.results),
                'passed': len([r for r in self.results if r.success]),
                'failed': len([r for r in self.results if not r.success]),
                'success_rate': (len([r for r in self.results if r.success]) / len(self.results)) * 100 if self.results else 0
            }
        }


async def main():
    """Main validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Network Monitoring Agent Installation Validator')
    parser.add_argument('--report', type=Path, help='Save validation report to file')
    parser.add_argument('--quiet', action='store_true', help='Minimal output')
    
    args = parser.parse_args()
    
    validator = AgentValidator()
    
    try:
        success = await validator.run_full_validation()
        
        # Save report if requested
        if args.report:
            report = validator.generate_report()
            with open(args.report, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nValidation report saved to {args.report}")
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nValidation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nValidation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())