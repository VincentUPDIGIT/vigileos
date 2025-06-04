#!/usr/bin/env python3
"""
Cross-platform installation script for Network Monitoring Agent.
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, Optional
import json
import argparse


class AgentInstaller:
    """Cross-platform agent installer."""
    
    def __init__(self):
        """Initialize installer."""
        self.system = platform.system().lower()
        self.project_root = Path(__file__).parent.parent
        self.install_locations = self._get_install_locations()
        
    def _get_install_locations(self) -> Dict[str, Path]:
        """Get platform-specific installation locations."""
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
            raise RuntimeError(f"Unsupported platform: {self.system}")
    
    def check_requirements(self) -> bool:
        """Check installation requirements."""
        print("Checking requirements...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            print("ERROR: Python 3.8 or higher is required")
            return False
        
        print(f"✓ Python {sys.version}")
        
        # Check if running as admin/root
        if not self._is_admin():
            print("ERROR: Installation requires administrator/root privileges")
            return False
        
        print("✓ Administrator privileges")
        
        # Check available disk space (at least 100MB)
        if not self._check_disk_space():
            print("ERROR: Insufficient disk space (at least 100MB required)")
            return False
        
        print("✓ Sufficient disk space")
        
        return True
    
    def _is_admin(self) -> bool:
        """Check if running with admin privileges."""
        try:
            if self.system == "windows":
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin()
            else:
                return os.geteuid() == 0
        except:
            return False
    
    def _check_disk_space(self) -> bool:
        """Check available disk space."""
        try:
            if self.system == "windows":
                import shutil
                _, _, free = shutil.disk_usage(self.install_locations['base'].parent)
            else:
                stat = os.statvfs(self.install_locations['base'].parent)
                free = stat.f_bavail * stat.f_frsize
            
            # Require at least 100MB
            return free > 100 * 1024 * 1024
        except:
            return True  # Assume OK if we can't check
    
    def create_directories(self):
        """Create installation directories."""
        print("Creating directories...")
        
        for name, path in self.install_locations.items():
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"✓ Created {name}: {path}")
                
                # Set permissions on Unix systems
                if self.system in ["linux", "darwin"]:
                    if name in ["data", "logs"]:
                        # Data and log directories should be writable by service user
                        os.chmod(path, 0o755)
                    else:
                        os.chmod(path, 0o755)
                        
            except Exception as e:
                print(f"ERROR: Failed to create {name} directory {path}: {e}")
                raise
    
    def install_files(self):
        """Install application files."""
        print("Installing files...")
        
        base_dir = self.install_locations['base']
        
        # Copy source code
        src_dir = base_dir / "src"
        if src_dir.exists():
            shutil.rmtree(src_dir)
        
        shutil.copytree(self.project_root / "src", src_dir)
        print(f"✓ Copied source code to {src_dir}")
        
        # Copy configuration
        config_dir = self.install_locations['config']
        default_config = self.project_root / "config" / "default_config.json"
        target_config = config_dir / "config.json"
        
        if not target_config.exists():
            shutil.copy2(default_config, target_config)
            print(f"✓ Copied default configuration to {target_config}")
        else:
            print(f"✓ Configuration already exists at {target_config}")
        
        # Copy requirements
        requirements_file = base_dir / "requirements.txt"
        shutil.copy2(self.project_root / "requirements.txt", requirements_file)
        print(f"✓ Copied requirements to {requirements_file}")
        
        # Create version file
        version_file = base_dir / "VERSION"
        with open(version_file, 'w') as f:
            f.write("1.0.0\n")
        print(f"✓ Created version file {version_file}")
    
    def install_dependencies(self):
        """Install Python dependencies."""
        print("Installing Python dependencies...")
        
        requirements_file = self.install_locations['base'] / "requirements.txt"
        
        try:
            # Use pip to install requirements
            cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("✓ Python dependencies installed successfully")
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to install dependencies: {e}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            raise
    
    def create_service_scripts(self):
        """Create service management scripts."""
        print("Creating service scripts...")
        
        base_dir = self.install_locations['base']
        bin_dir = self.install_locations['bin']
        
        if self.system == "linux":
            from src.services.linux_service import LinuxService
            service = LinuxService()
            script_path = service.create_service_script(base_dir)
            
            # Create symlink in /usr/local/bin
            symlink_path = bin_dir / "network-agent"
            if symlink_path.exists():
                symlink_path.unlink()
            symlink_path.symlink_to(script_path)
            
        elif self.system == "darwin":
            from src.services.macos_service import MacOSService
            service = MacOSService()
            script_path = service.create_service_script(base_dir)
            
            # Create symlink in /usr/local/bin
            symlink_path = bin_dir / "network-agent"
            if symlink_path.exists():
                symlink_path.unlink()
            symlink_path.symlink_to(script_path)
            
        elif self.system == "windows":
            from src.services.windows_service import WindowsServiceManager
            manager = WindowsServiceManager()
            script_path = manager.create_service_script(base_dir)
            installer_path = manager.create_installer_script(base_dir)
            
        print(f"✓ Service scripts created")
    
    def install_service(self):
        """Install system service."""
        print("Installing system service...")
        
        base_dir = self.install_locations['base']
        config_file = self.install_locations['config'] / "config.json"
        
        try:
            if self.system == "linux":
                from src.services.linux_service import LinuxService
                service = LinuxService()
                success = service.install_service(base_dir, config_file)
                
            elif self.system == "darwin":
                from src.services.macos_service import MacOSService
                service = MacOSService()
                success = service.install_service(base_dir, config_file)
                
            elif self.system == "windows":
                from src.services.windows_service import WindowsServiceManager
                manager = WindowsServiceManager()
                success = manager.install_service(base_dir, config_file)
            
            if success:
                print("✓ System service installed successfully")
            else:
                print("WARNING: Service installation failed")
                
        except Exception as e:
            print(f"WARNING: Service installation failed: {e}")
    
    def configure_firewall(self):
        """Configure firewall rules if needed."""
        print("Configuring firewall...")
        
        # This is optional and platform-specific
        try:
            if self.system == "linux":
                # Check if ufw is available
                result = subprocess.run(['which', 'ufw'], capture_output=True)
                if result.returncode == 0:
                    # Allow SNMP and SSH ports
                    subprocess.run(['ufw', 'allow', '161/udp'], check=False)
                    subprocess.run(['ufw', 'allow', '22/tcp'], check=False)
                    print("✓ UFW firewall rules added")
                
            elif self.system == "darwin":
                # macOS firewall configuration would go here
                print("✓ Firewall configuration skipped (manual configuration may be needed)")
                
            elif self.system == "windows":
                # Windows firewall configuration would go here
                print("✓ Firewall configuration skipped (manual configuration may be needed)")
                
        except Exception as e:
            print(f"WARNING: Firewall configuration failed: {e}")
    
    def create_uninstaller(self):
        """Create uninstaller script."""
        print("Creating uninstaller...")
        
        base_dir = self.install_locations['base']
        
        if self.system == "windows":
            uninstaller_content = f"""@echo off
echo Uninstalling Network Monitoring Agent...

REM Stop and remove service
python -m src.services.windows_service stop
python -m src.services.windows_service uninstall

REM Remove files
rmdir /s /q "{base_dir}"
rmdir /s /q "{self.install_locations['config']}"
rmdir /s /q "{self.install_locations['data']}"
rmdir /s /q "{self.install_locations['logs']}"

echo Uninstallation completed.
pause
"""
            uninstaller_path = base_dir / "uninstall.bat"
        else:
            uninstaller_content = f"""#!/bin/bash
echo "Uninstalling Network Monitoring Agent..."

# Stop and remove service
if [ "{self.system}" = "linux" ]; then
    python3 -m src.services.linux_service stop
    python3 -m src.services.linux_service uninstall
elif [ "{self.system}" = "darwin" ]; then
    python3 -m src.services.macos_service stop
    python3 -m src.services.macos_service uninstall
fi

# Remove files
rm -rf "{base_dir}"
rm -rf "{self.install_locations['config']}"
rm -rf "{self.install_locations['data']}"
rm -rf "{self.install_locations['logs']}"
rm -f "{self.install_locations['bin']}/network-agent"

echo "Uninstallation completed."
"""
            uninstaller_path = base_dir / "uninstall.sh"
            
        with open(uninstaller_path, 'w') as f:
            f.write(uninstaller_content)
        
        # Make executable on Unix systems
        if self.system in ["linux", "darwin"]:
            os.chmod(uninstaller_path, 0o755)
        
        print(f"✓ Uninstaller created at {uninstaller_path}")
    
    def post_install_setup(self):
        """Perform post-installation setup."""
        print("Performing post-installation setup...")
        
        # Update configuration with detected settings
        config_file = self.install_locations['config'] / "config.json"
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Update paths
            config['agent']['data_dir'] = str(self.install_locations['data'])
            config['logging']['file_logging'] = True
            
            # Platform-specific settings
            if self.system == "windows":
                config['collection']['enabled_collectors'] = ["snmp", "web", "api", "system"]
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✓ Configuration updated")
            
        except Exception as e:
            print(f"WARNING: Configuration update failed: {e}")
    
    def install(self, start_service: bool = True):
        """Perform complete installation."""
        print(f"Installing Network Monitoring Agent on {platform.system()}...")
        print(f"Installation directory: {self.install_locations['base']}")
        
        try:
            # Check requirements
            if not self.check_requirements():
                return False
            
            # Create directories
            self.create_directories()
            
            # Install files
            self.install_files()
            
            # Install dependencies
            self.install_dependencies()
            
            # Create service scripts
            self.create_service_scripts()
            
            # Install service
            self.install_service()
            
            # Configure firewall
            self.configure_firewall()
            
            # Create uninstaller
            self.create_uninstaller()
            
            # Post-install setup
            self.post_install_setup()
            
            print("\n" + "="*50)
            print("Installation completed successfully!")
            print("="*50)
            print(f"Installation directory: {self.install_locations['base']}")
            print(f"Configuration file: {self.install_locations['config']}/config.json")
            print(f"Log directory: {self.install_locations['logs']}")
            print(f"Data directory: {self.install_locations['data']}")
            
            if start_service:
                print("\nStarting service...")
                self.start_service()
            
            print("\nNext steps:")
            print("1. Edit the configuration file to match your environment")
            print("2. Configure backend connection settings")
            print("3. Add devices to monitor")
            print("4. Start the service if not already running")
            
            return True
            
        except Exception as e:
            print(f"\nInstallation failed: {e}")
            return False
    
    def start_service(self):
        """Start the installed service."""
        try:
            if self.system == "linux":
                subprocess.run(['systemctl', 'start', 'network-monitoring-agent'], check=True)
            elif self.system == "darwin":
                subprocess.run(['launchctl', 'start', 'com.company.network-monitoring-agent'], check=True)
            elif self.system == "windows":
                subprocess.run(['sc', 'start', 'NetworkMonitoringAgent'], check=True)
            
            print("✓ Service started successfully")
            
        except Exception as e:
            print(f"WARNING: Failed to start service: {e}")


def main():
    """Main installation function."""
    parser = argparse.ArgumentParser(description='Network Monitoring Agent Installer')
    parser.add_argument('--no-service', action='store_true', 
                       help='Skip service installation')
    parser.add_argument('--no-start', action='store_true',
                       help='Do not start service after installation')
    
    args = parser.parse_args()
    
    installer = AgentInstaller()
    
    try:
        success = installer.install(start_service=not args.no_start)
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nInstallation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()