"""
macOS launchd service implementation.
"""

import os
import sys
import subprocess
import asyncio
import plistlib
from pathlib import Path
from typing import Dict, Any, Optional

from agent.main_agent import NetworkMonitoringAgent
from utils.logger import setup_application_logging


class MacOSService:
    """macOS launchd service for network monitoring agent."""
    
    SERVICE_NAME = "com.company.network-monitoring-agent"
    SERVICE_USER = "_networkagent"
    SERVICE_GROUP = "_networkagent"
    
    def __init__(self):
        """Initialize macOS service."""
        self.logger = setup_application_logging("network_agent_service")
        self.agent: Optional[NetworkMonitoringAgent] = None
    
    def create_launchd_plist(self, install_dir: Path, config_file: Path = None) -> Dict[str, Any]:
        """
        Create launchd plist configuration.
        
        Args:
            install_dir: Installation directory
            config_file: Configuration file path
            
        Returns:
            Dict[str, Any]: Plist configuration
        """
        exec_path = install_dir / "bin" / "network-agent"
        program_arguments = [str(exec_path)]
        
        if config_file:
            program_arguments.extend(["--config", str(config_file)])
        
        plist_config = {
            'Label': self.SERVICE_NAME,
            'ProgramArguments': program_arguments,
            'RunAtLoad': True,
            'KeepAlive': {
                'SuccessfulExit': False,
                'Crashed': True
            },
            'StandardOutPath': '/var/log/network-agent/stdout.log',
            'StandardErrorPath': '/var/log/network-agent/stderr.log',
            'WorkingDirectory': str(install_dir),
            'UserName': self.SERVICE_USER,
            'GroupName': self.SERVICE_GROUP,
            'ProcessType': 'Background',
            'ThrottleInterval': 10,
            'ExitTimeOut': 30,
            'EnvironmentVariables': {
                'PATH': '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
                'PYTHONPATH': str(install_dir / 'lib')
            }
        }
        
        return plist_config
    
    def install_service(self, install_dir: Path, config_file: Path = None) -> bool:
        """
        Install launchd service.
        
        Args:
            install_dir: Installation directory
            config_file: Configuration file path
            
        Returns:
            bool: True if installation successful
        """
        try:
            # Create service user and group
            self._create_service_user()
            
            # Create plist configuration
            plist_config = self.create_launchd_plist(install_dir, config_file)
            
            # Write plist file
            plist_path = Path(f"/Library/LaunchDaemons/{self.SERVICE_NAME}.plist")
            with open(plist_path, 'wb') as f:
                plistlib.dump(plist_config, f)
            
            # Set permissions
            os.chmod(plist_path, 0o644)
            subprocess.run(['chown', 'root:wheel', str(plist_path)], check=True)
            
            # Load service
            subprocess.run(['launchctl', 'load', str(plist_path)], check=True)
            
            self.logger.info(f"Service {self.SERVICE_NAME} installed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Service installation failed: {e}")
            return False
    
    def _create_service_user(self):
        """Create service user and group."""
        try:
            # Check if user already exists
            result = subprocess.run(['dscl', '.', 'read', f'/Users/{self.SERVICE_USER}'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info(f"User {self.SERVICE_USER} already exists")
                return
            
            # Find available UID/GID
            uid_gid = self._find_available_uid()
            
            # Create group
            subprocess.run([
                'dscl', '.', 'create', f'/Groups/{self.SERVICE_GROUP}',
                'PrimaryGroupID', str(uid_gid)
            ], check=True)
            
            # Create user
            subprocess.run([
                'dscl', '.', 'create', f'/Users/{self.SERVICE_USER}',
                'UniqueID', str(uid_gid),
                'PrimaryGroupID', str(uid_gid),
                'UserShell', '/usr/bin/false',
                'RealName', 'Network Monitoring Agent',
                'NFSHomeDirectory', '/var/lib/network-agent'
            ], check=True)
            
            # Create directories
            directories = [
                '/var/lib/network-agent',
                '/var/log/network-agent',
                '/etc/network-agent'
            ]
            
            for directory in directories:
                Path(directory).mkdir(parents=True, exist_ok=True)
                subprocess.run(['chown', f'{self.SERVICE_USER}:{self.SERVICE_GROUP}', directory])
                subprocess.run(['chmod', '755', directory])
            
        except Exception as e:
            self.logger.warning(f"User creation failed (may already exist): {e}")
    
    def _find_available_uid(self) -> int:
        """Find available UID/GID for service user."""
        # Start from 200 (system user range)
        for uid in range(200, 300):
            result = subprocess.run(['dscl', '.', 'read', f'/Users', 'UniqueID'], 
                                  capture_output=True, text=True)
            if str(uid) not in result.stdout:
                return uid
        
        # Fallback to 250
        return 250
    
    def uninstall_service(self) -> bool:
        """
        Uninstall launchd service.
        
        Returns:
            bool: True if uninstallation successful
        """
        try:
            plist_path = Path(f"/Library/LaunchDaemons/{self.SERVICE_NAME}.plist")
            
            # Unload service
            subprocess.run(['launchctl', 'unload', str(plist_path)], check=False)
            
            # Remove plist file
            if plist_path.exists():
                plist_path.unlink()
            
            self.logger.info(f"Service {self.SERVICE_NAME} uninstalled successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Service uninstallation failed: {e}")
            return False
    
    def start_service(self) -> bool:
        """Start the service."""
        try:
            subprocess.run(['launchctl', 'start', self.SERVICE_NAME], check=True)
            self.logger.info(f"Service {self.SERVICE_NAME} started")
            return True
        except Exception as e:
            self.logger.error(f"Service start failed: {e}")
            return False
    
    def stop_service(self) -> bool:
        """Stop the service."""
        try:
            subprocess.run(['launchctl', 'stop', self.SERVICE_NAME], check=True)
            self.logger.info(f"Service {self.SERVICE_NAME} stopped")
            return True
        except Exception as e:
            self.logger.error(f"Service stop failed: {e}")
            return False
    
    def restart_service(self) -> bool:
        """Restart the service."""
        try:
            self.stop_service()
            self.start_service()
            self.logger.info(f"Service {self.SERVICE_NAME} restarted")
            return True
        except Exception as e:
            self.logger.error(f"Service restart failed: {e}")
            return False
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get service status."""
        try:
            # Check if service is loaded
            result = subprocess.run(
                ['launchctl', 'list', self.SERVICE_NAME],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                # Parse output
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 1:
                    parts = lines[0].split('\t')
                    if len(parts) >= 3:
                        pid = parts[0] if parts[0] != '-' else None
                        exit_code = parts[1] if parts[1] != '-' else None
                        label = parts[2]
                        
                        return {
                            'loaded': True,
                            'running': pid is not None,
                            'pid': int(pid) if pid else None,
                            'exit_code': int(exit_code) if exit_code else None,
                            'label': label
                        }
            
            return {
                'loaded': False,
                'running': False,
                'error': result.stderr if result.stderr else 'Service not found'
            }
            
        except Exception as e:
            return {
                'loaded': False,
                'running': False,
                'error': str(e)
            }
    
    async def run_service(self, config_file: Path = None):
        """
        Run the service (called by launchd).
        
        Args:
            config_file: Configuration file path
        """
        try:
            self.logger.info("Starting Network Monitoring Agent service")
            
            # Create and start agent
            self.agent = NetworkMonitoringAgent(config_file)
            await self.agent.start()
            
        except Exception as e:
            self.logger.error(f"Service run failed: {e}")
            sys.exit(1)
    
    def create_service_script(self, install_dir: Path) -> Path:
        """
        Create service startup script.
        
        Args:
            install_dir: Installation directory
            
        Returns:
            Path: Script file path
        """
        script_content = f"""#!/usr/bin/env python3
import sys
import asyncio
from pathlib import Path

# Add installation directory to Python path
sys.path.insert(0, '{install_dir}/lib')

from src.services.macos_service import MacOSService

async def main():
    service = MacOSService()
    config_file = None
    
    # Parse command line arguments
    if len(sys.argv) > 2 and sys.argv[1] == '--config':
        config_file = Path(sys.argv[2])
    
    await service.run_service(config_file)

if __name__ == '__main__':
    asyncio.run(main())
"""
        
        script_path = install_dir / "bin" / "network-agent"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(script_path, 0o755)
        
        return script_path
    
    def create_installer_script(self, install_dir: Path) -> Path:
        """
        Create installer script.
        
        Args:
            install_dir: Installation directory
            
        Returns:
            Path: Installer script path
        """
        script_content = f"""#!/bin/bash
echo "Installing Network Monitoring Agent Service..."

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "This script requires root privileges."
    echo "Please run with sudo."
    exit 1
fi

# Install service
cd "{install_dir}"
python3 -m src.services.macos_service install --install-dir "{install_dir}"

if [ $? -eq 0 ]; then
    echo "Service installed successfully."
    echo "Starting service..."
    python3 -m src.services.macos_service start
    if [ $? -eq 0 ]; then
        echo "Service started successfully."
    else
        echo "Failed to start service."
    fi
else
    echo "Service installation failed."
fi
"""
        
        script_path = install_dir / "install_service.sh"
        
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(script_path, 0o755)
        
        return script_path


def main():
    """Service management CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='macOS Service Management')
    parser.add_argument('action', choices=['install', 'uninstall', 'start', 'stop', 'restart', 'status'])
    parser.add_argument('--install-dir', type=Path, default=Path('/opt/network-agent'))
    parser.add_argument('--config', type=Path, help='Configuration file path')
    
    args = parser.parse_args()
    
    service = MacOSService()
    
    if args.action == 'install':
        success = service.install_service(args.install_dir, args.config)
        sys.exit(0 if success else 1)
    elif args.action == 'uninstall':
        success = service.uninstall_service()
        sys.exit(0 if success else 1)
    elif args.action == 'start':
        success = service.start_service()
        sys.exit(0 if success else 1)
    elif args.action == 'stop':
        success = service.stop_service()
        sys.exit(0 if success else 1)
    elif args.action == 'restart':
        success = service.restart_service()
        sys.exit(0 if success else 1)
    elif args.action == 'status':
        status = service.get_service_status()
        print(f"Loaded: {status['loaded']}")
        print(f"Running: {status['running']}")
        if 'pid' in status and status['pid']:
            print(f"PID: {status['pid']}")
        if 'error' in status:
            print(f"Error: {status['error']}")


if __name__ == '__main__':
    main()