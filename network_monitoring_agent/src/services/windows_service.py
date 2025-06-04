"""
Windows service implementation.
"""

import sys
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    WINDOWS_SERVICE_AVAILABLE = True
except ImportError:
    WINDOWS_SERVICE_AVAILABLE = False

from agent.main_agent import NetworkMonitoringAgent
from utils.logger import setup_application_logging


class WindowsService(win32serviceutil.ServiceFramework if WINDOWS_SERVICE_AVAILABLE else object):
    """Windows service for network monitoring agent."""
    
    _svc_name_ = "NetworkMonitoringAgent"
    _svc_display_name_ = "Network Monitoring Agent"
    _svc_description_ = "Cross-platform network monitoring and device management agent"
    
    def __init__(self, args=None):
        """Initialize Windows service."""
        if WINDOWS_SERVICE_AVAILABLE:
            win32serviceutil.ServiceFramework.__init__(self, args)
        
        self.logger = setup_application_logging("network_agent_service")
        self.agent: Optional[NetworkMonitoringAgent] = None
        self.stop_event = None
        self.config_file = None
        
        if WINDOWS_SERVICE_AVAILABLE:
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
    
    def SvcStop(self):
        """Handle service stop request."""
        if not WINDOWS_SERVICE_AVAILABLE:
            return
        
        self.logger.info("Service stop requested")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
    
    def SvcDoRun(self):
        """Main service execution."""
        if not WINDOWS_SERVICE_AVAILABLE:
            return
        
        try:
            self.logger.info("Starting Network Monitoring Agent service")
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            
            # Run the agent
            asyncio.run(self._run_agent())
            
        except Exception as e:
            self.logger.error(f"Service execution failed: {e}")
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_ERROR_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, str(e))
            )
    
    async def _run_agent(self):
        """Run the monitoring agent."""
        try:
            # Load configuration
            config_file = self._get_config_file()
            
            # Create and start agent
            self.agent = NetworkMonitoringAgent(config_file)
            
            # Start agent in background task
            agent_task = asyncio.create_task(self.agent.start())
            
            # Wait for stop event
            while True:
                if WINDOWS_SERVICE_AVAILABLE:
                    # Check if stop was requested
                    if win32event.WaitForSingleObject(self.hWaitStop, 1000) == win32event.WAIT_OBJECT_0:
                        break
                else:
                    await asyncio.sleep(1)
            
            # Stop agent
            if self.agent:
                await self.agent.stop()
            
            # Wait for agent task to complete
            if not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except asyncio.CancelledError:
                    pass
            
        except Exception as e:
            self.logger.error(f"Agent execution failed: {e}")
            raise
    
    def _get_config_file(self) -> Optional[Path]:
        """Get configuration file path."""
        # Check common locations
        config_locations = [
            Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / 'NetworkAgent' / 'config.json',
            Path(sys.executable).parent / 'config.json',
            Path.cwd() / 'config.json'
        ]
        
        for config_path in config_locations:
            if config_path.exists():
                return config_path
        
        return None


class WindowsServiceManager:
    """Windows service management utilities."""
    
    def __init__(self):
        """Initialize service manager."""
        self.logger = setup_application_logging("service_manager")
        
        if not WINDOWS_SERVICE_AVAILABLE:
            self.logger.warning("Windows service modules not available")
    
    def install_service(self, install_dir: Path, config_file: Path = None) -> bool:
        """
        Install Windows service.
        
        Args:
            install_dir: Installation directory
            config_file: Configuration file path
            
        Returns:
            bool: True if installation successful
        """
        if not WINDOWS_SERVICE_AVAILABLE:
            self.logger.error("Windows service modules not available")
            return False
        
        try:
            # Create service directories
            self._create_service_directories()
            
            # Install service
            python_exe = sys.executable
            script_path = install_dir / "src" / "services" / "windows_service.py"
            
            win32serviceutil.InstallService(
                pythonClassString=f"{script_path}::WindowsService",
                serviceName=WindowsService._svc_name_,
                displayName=WindowsService._svc_display_name_,
                description=WindowsService._svc_description_,
                exeName=python_exe
            )
            
            self.logger.info(f"Service {WindowsService._svc_name_} installed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Service installation failed: {e}")
            return False
    
    def _create_service_directories(self):
        """Create service directories."""
        directories = [
            Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / 'NetworkAgent',
            Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / 'NetworkAgent' / 'logs',
            Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / 'NetworkAgent' / 'data'
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def uninstall_service(self) -> bool:
        """
        Uninstall Windows service.
        
        Returns:
            bool: True if uninstallation successful
        """
        if not WINDOWS_SERVICE_AVAILABLE:
            self.logger.error("Windows service modules not available")
            return False
        
        try:
            # Stop service first
            self.stop_service()
            
            # Uninstall service
            win32serviceutil.RemoveService(WindowsService._svc_name_)
            
            self.logger.info(f"Service {WindowsService._svc_name_} uninstalled successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Service uninstallation failed: {e}")
            return False
    
    def start_service(self) -> bool:
        """Start the service."""
        if not WINDOWS_SERVICE_AVAILABLE:
            return False
        
        try:
            win32serviceutil.StartService(WindowsService._svc_name_)
            self.logger.info(f"Service {WindowsService._svc_name_} started")
            return True
        except Exception as e:
            self.logger.error(f"Service start failed: {e}")
            return False
    
    def stop_service(self) -> bool:
        """Stop the service."""
        if not WINDOWS_SERVICE_AVAILABLE:
            return False
        
        try:
            win32serviceutil.StopService(WindowsService._svc_name_)
            self.logger.info(f"Service {WindowsService._svc_name_} stopped")
            return True
        except Exception as e:
            self.logger.error(f"Service stop failed: {e}")
            return False
    
    def restart_service(self) -> bool:
        """Restart the service."""
        if not WINDOWS_SERVICE_AVAILABLE:
            return False
        
        try:
            win32serviceutil.RestartService(WindowsService._svc_name_)
            self.logger.info(f"Service {WindowsService._svc_name_} restarted")
            return True
        except Exception as e:
            self.logger.error(f"Service restart failed: {e}")
            return False
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get service status."""
        if not WINDOWS_SERVICE_AVAILABLE:
            return {'error': 'Windows service modules not available'}
        
        try:
            status = win32serviceutil.QueryServiceStatus(WindowsService._svc_name_)
            
            status_map = {
                win32service.SERVICE_STOPPED: 'stopped',
                win32service.SERVICE_START_PENDING: 'start_pending',
                win32service.SERVICE_STOP_PENDING: 'stop_pending',
                win32service.SERVICE_RUNNING: 'running',
                win32service.SERVICE_CONTINUE_PENDING: 'continue_pending',
                win32service.SERVICE_PAUSE_PENDING: 'pause_pending',
                win32service.SERVICE_PAUSED: 'paused'
            }
            
            return {
                'status': status_map.get(status[1], 'unknown'),
                'status_code': status[1],
                'controls_accepted': status[2],
                'win32_exit_code': status[3],
                'service_exit_code': status[4],
                'check_point': status[5],
                'wait_hint': status[6]
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def create_service_script(self, install_dir: Path) -> Path:
        """
        Create service startup script.
        
        Args:
            install_dir: Installation directory
            
        Returns:
            Path: Script file path
        """
        script_content = f"""@echo off
cd /d "{install_dir}"
python -m src.services.windows_service
"""
        
        script_path = install_dir / "bin" / "network-agent.bat"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        return script_path
    
    def create_installer_script(self, install_dir: Path) -> Path:
        """
        Create installer script.
        
        Args:
            install_dir: Installation directory
            
        Returns:
            Path: Installer script path
        """
        script_content = f"""@echo off
echo Installing Network Monitoring Agent Service...

REM Check for admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script requires administrator privileges.
    echo Please run as administrator.
    pause
    exit /b 1
)

REM Install service
cd /d "{install_dir}"
python -m src.services.windows_service install

if %errorLevel% equ 0 (
    echo Service installed successfully.
    echo Starting service...
    python -m src.services.windows_service start
    if %errorLevel% equ 0 (
        echo Service started successfully.
    ) else (
        echo Failed to start service.
    )
) else (
    echo Service installation failed.
)

pause
"""
        
        script_path = install_dir / "install_service.bat"
        
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        return script_path


def main():
    """Service management CLI."""
    if not WINDOWS_SERVICE_AVAILABLE:
        print("Windows service modules not available")
        sys.exit(1)
    
    if len(sys.argv) == 1:
        # Run as service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(WindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Handle command line arguments
        import argparse
        
        parser = argparse.ArgumentParser(description='Windows Service Management')
        parser.add_argument('action', choices=['install', 'uninstall', 'start', 'stop', 'restart', 'status'])
        parser.add_argument('--install-dir', type=Path, default=Path('C:\\Program Files\\NetworkAgent'))
        parser.add_argument('--config', type=Path, help='Configuration file path')
        
        args = parser.parse_args()
        
        manager = WindowsServiceManager()
        
        if args.action == 'install':
            success = manager.install_service(args.install_dir, args.config)
            sys.exit(0 if success else 1)
        elif args.action == 'uninstall':
            success = manager.uninstall_service()
            sys.exit(0 if success else 1)
        elif args.action == 'start':
            success = manager.start_service()
            sys.exit(0 if success else 1)
        elif args.action == 'stop':
            success = manager.stop_service()
            sys.exit(0 if success else 1)
        elif args.action == 'restart':
            success = manager.restart_service()
            sys.exit(0 if success else 1)
        elif args.action == 'status':
            status = manager.get_service_status()
            if 'error' in status:
                print(f"Error: {status['error']}")
            else:
                print(f"Status: {status['status']}")
                print(f"Status Code: {status['status_code']}")


if __name__ == '__main__':
    main()