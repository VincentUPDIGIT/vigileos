"""
Linux systemd service implementation.
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from agent.main_agent import NetworkMonitoringAgent
from utils.logger import setup_application_logging


class LinuxService:
    """Linux systemd service for network monitoring agent."""
    
    SERVICE_NAME = "network-monitoring-agent"
    SERVICE_USER = "network-agent"
    SERVICE_GROUP = "network-agent"
    
    def __init__(self):
        """Initialize Linux service."""
        self.logger = setup_application_logging("network_agent_service")
        self.agent: Optional[NetworkMonitoringAgent] = None
    
    def create_service_unit(self, install_dir: Path, config_file: Path = None) -> str:
        """
        Create systemd service unit file content.
        
        Args:
            install_dir: Installation directory
            config_file: Configuration file path
            
        Returns:
            str: Service unit file content
        """
        exec_start = install_dir / "bin" / "network-agent"
        config_arg = f" --config {config_file}" if config_file else ""
        
        unit_content = f"""[Unit]
Description=Network Monitoring Agent
Documentation=https://github.com/company/network-monitoring-agent
After=network.target network-online.target
Wants=network-online.target
RequiresMountsFor={install_dir}

[Service]
Type=simple
User={self.SERVICE_USER}
Group={self.SERVICE_GROUP}
ExecStart={exec_start}{config_arg}
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGTERM

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/network-agent /var/lib/network-agent /etc/network-agent
CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN CAP_SYS_ADMIN
AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN

# Environment
Environment=PYTHONPATH={install_dir}/lib
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Working directory
WorkingDirectory={install_dir}

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=network-agent

[Install]
WantedBy=multi-user.target
"""
        return unit_content
    
    def install_service(self, install_dir: Path, config_file: Path = None) -> bool:
        """
        Install systemd service.
        
        Args:
            install_dir: Installation directory
            config_file: Configuration file path
            
        Returns:
            bool: True if installation successful
        """
        try:
            # Create service user and group
            self._create_service_user()
            
            # Create service unit file
            unit_content = self.create_service_unit(install_dir, config_file)
            unit_file_path = Path(f"/etc/systemd/system/{self.SERVICE_NAME}.service")
            
            with open(unit_file_path, 'w') as f:
                f.write(unit_content)
            
            # Set permissions
            os.chmod(unit_file_path, 0o644)
            
            # Reload systemd
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            
            # Enable service
            subprocess.run(['systemctl', 'enable', self.SERVICE_NAME], check=True)
            
            self.logger.info(f"Service {self.SERVICE_NAME} installed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Service installation failed: {e}")
            return False
    
    def _create_service_user(self):
        """Create service user and group."""
        try:
            # Create group
            subprocess.run(['groupadd', '-r', self.SERVICE_GROUP], 
                         check=False)  # Don't fail if group exists
            
            # Create user
            subprocess.run([
                'useradd', '-r', '-g', self.SERVICE_GROUP,
                '-d', '/var/lib/network-agent',
                '-s', '/bin/false',
                '-c', 'Network Monitoring Agent',
                self.SERVICE_USER
            ], check=False)  # Don't fail if user exists
            
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
    
    def uninstall_service(self) -> bool:
        """
        Uninstall systemd service.
        
        Returns:
            bool: True if uninstallation successful
        """
        try:
            # Stop service
            subprocess.run(['systemctl', 'stop', self.SERVICE_NAME], check=False)
            
            # Disable service
            subprocess.run(['systemctl', 'disable', self.SERVICE_NAME], check=False)
            
            # Remove unit file
            unit_file_path = Path(f"/etc/systemd/system/{self.SERVICE_NAME}.service")
            if unit_file_path.exists():
                unit_file_path.unlink()
            
            # Reload systemd
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            
            self.logger.info(f"Service {self.SERVICE_NAME} uninstalled successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Service uninstallation failed: {e}")
            return False
    
    def start_service(self) -> bool:
        """Start the service."""
        try:
            subprocess.run(['systemctl', 'start', self.SERVICE_NAME], check=True)
            self.logger.info(f"Service {self.SERVICE_NAME} started")
            return True
        except Exception as e:
            self.logger.error(f"Service start failed: {e}")
            return False
    
    def stop_service(self) -> bool:
        """Stop the service."""
        try:
            subprocess.run(['systemctl', 'stop', self.SERVICE_NAME], check=True)
            self.logger.info(f"Service {self.SERVICE_NAME} stopped")
            return True
        except Exception as e:
            self.logger.error(f"Service stop failed: {e}")
            return False
    
    def restart_service(self) -> bool:
        """Restart the service."""
        try:
            subprocess.run(['systemctl', 'restart', self.SERVICE_NAME], check=True)
            self.logger.info(f"Service {self.SERVICE_NAME} restarted")
            return True
        except Exception as e:
            self.logger.error(f"Service restart failed: {e}")
            return False
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get service status."""
        try:
            result = subprocess.run(
                ['systemctl', 'status', self.SERVICE_NAME],
                capture_output=True, text=True
            )
            
            is_active = subprocess.run(
                ['systemctl', 'is-active', self.SERVICE_NAME],
                capture_output=True, text=True
            ).stdout.strip() == 'active'
            
            is_enabled = subprocess.run(
                ['systemctl', 'is-enabled', self.SERVICE_NAME],
                capture_output=True, text=True
            ).stdout.strip() == 'enabled'
            
            return {
                'active': is_active,
                'enabled': is_enabled,
                'status_output': result.stdout,
                'return_code': result.returncode
            }
            
        except Exception as e:
            return {
                'active': False,
                'enabled': False,
                'error': str(e)
            }
    
    async def run_service(self, config_file: Path = None):
        """
        Run the service (called by systemd).
        
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

from src.services.linux_service import LinuxService

async def main():
    service = LinuxService()
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


def main():
    """Service management CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Linux Service Management')
    parser.add_argument('action', choices=['install', 'uninstall', 'start', 'stop', 'restart', 'status'])
    parser.add_argument('--install-dir', type=Path, default=Path('/opt/network-agent'))
    parser.add_argument('--config', type=Path, help='Configuration file path')
    
    args = parser.parse_args()
    
    service = LinuxService()
    
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
        print(f"Active: {status['active']}")
        print(f"Enabled: {status['enabled']}")
        if 'error' in status:
            print(f"Error: {status['error']}")
        else:
            print(status['status_output'])


if __name__ == '__main__':
    main()