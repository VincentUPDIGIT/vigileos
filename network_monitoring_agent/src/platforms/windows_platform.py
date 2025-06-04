"""
Windows-specific platform implementation.
"""

import os
import sys
import subprocess
import time
import json
import ctypes
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

import psutil

# Windows-specific imports (only available on Windows)
if sys.platform == "win32":
    try:
        import win32api
        import win32con
        import win32service
        import win32serviceutil
        import wmi
        import winreg
    except ImportError:
        # Fallback if Windows-specific modules are not available
        win32api = None
        win32con = None
        win32service = None
        win32serviceutil = None
        wmi = None
        winreg = None

from platforms.base_platform import (
    BasePlatform, SystemMetrics, NetworkInterface, ProcessInfo, 
    ServiceInfo, ServiceStatus, TunnelConfig, TunnelType, PlatformError
)


class WindowsPlatform(BasePlatform):
    """Windows-specific platform implementation."""

    def __init__(self):
        super().__init__()
        self._wmi_available = self._check_wmi_available()

    def _get_platform_name(self) -> str:
        return "windows"

    def _check_wmi_available(self) -> bool:
        """Check if WMI is available."""
        try:
            if wmi is None:
                return False
            wmi.WMI()
            return True
        except Exception:
            return False

    # System Information Methods
    def get_system_metrics(self) -> SystemMetrics:
        """Get comprehensive system metrics for Windows."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics (C: drive)
            disk = psutil.disk_usage('C:')
            
            # Boot time
            boot_time = int(psutil.boot_time())
            uptime = int(time.time() - boot_time)
            
            # Windows doesn't have load average, use CPU count as approximation
            load_average = [cpu_percent / 100.0 * psutil.cpu_count()] * 3
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_total=memory.total,
                memory_used=memory.used,
                disk_percent=disk.percent,
                disk_total=disk.total,
                disk_used=disk.used,
                load_average=load_average,
                uptime=uptime,
                boot_time=boot_time
            )
        except Exception as e:
            raise PlatformError(f"Failed to get system metrics: {e}", platform="windows")

    def get_network_interfaces(self) -> List[NetworkInterface]:
        """Get network interface information for Windows."""
        try:
            interfaces = []
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            net_io_counters = psutil.net_io_counters(pernic=True)
            
            for interface_name, addresses in net_if_addrs.items():
                # Skip loopback interface
                if 'loopback' in interface_name.lower():
                    continue
                
                ip_addresses = []
                mac_address = ""
                
                for addr in addresses:
                    if addr.family == psutil.AF_LINK:  # MAC address
                        mac_address = addr.address
                    elif addr.family in (psutil.AF_INET, psutil.AF_INET6):  # IP addresses
                        ip_addresses.append(addr.address)
                
                # Get interface statistics
                stats = net_if_stats.get(interface_name)
                io_counters = net_io_counters.get(interface_name)
                
                interface = NetworkInterface(
                    name=interface_name,
                    ip_addresses=ip_addresses,
                    mac_address=mac_address,
                    status="up" if stats and stats.isup else "down",
                    speed=stats.speed if stats else None,
                    mtu=stats.mtu if stats else None,
                    rx_bytes=io_counters.bytes_recv if io_counters else None,
                    tx_bytes=io_counters.bytes_sent if io_counters else None,
                    rx_packets=io_counters.packets_recv if io_counters else None,
                    tx_packets=io_counters.packets_sent if io_counters else None
                )
                interfaces.append(interface)
            
            return interfaces
        except Exception as e:
            raise PlatformError(f"Failed to get network interfaces: {e}", platform="windows")

    def get_running_processes(self, limit: Optional[int] = None) -> List[ProcessInfo]:
        """Get running process information for Windows."""
        try:
            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 
                                           'memory_info', 'status', 'create_time', 'cmdline', 'username']):
                try:
                    pinfo = proc.info
                    process = ProcessInfo(
                        pid=pinfo['pid'],
                        name=pinfo['name'],
                        cpu_percent=pinfo['cpu_percent'] or 0.0,
                        memory_percent=pinfo['memory_percent'] or 0.0,
                        memory_rss=pinfo['memory_info'].rss if pinfo['memory_info'] else 0,
                        status=pinfo['status'],
                        create_time=pinfo['create_time'],
                        cmdline=pinfo['cmdline'] or [],
                        username=pinfo['username']
                    )
                    processes.append(process)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by CPU usage (descending)
            processes.sort(key=lambda x: x.cpu_percent, reverse=True)
            
            if limit:
                processes = processes[:limit]
            
            return processes
        except Exception as e:
            raise PlatformError(f"Failed to get running processes: {e}", platform="windows")

    def get_system_services(self) -> List[ServiceInfo]:
        """Get system service information for Windows."""
        try:
            services = []
            
            if win32service is not None:
                # Use Windows Service API
                try:
                    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ENUMERATE_SERVICE)
                    service_list = win32service.EnumServicesStatus(scm)
                    
                    for service in service_list:
                        service_name = service[0]
                        display_name = service[1]
                        service_status = service[2]
                        
                        # Map Windows service states to our ServiceStatus enum
                        state = service_status[1]
                        if state == win32service.SERVICE_RUNNING:
                            status = ServiceStatus.RUNNING
                        elif state == win32service.SERVICE_STOPPED:
                            status = ServiceStatus.STOPPED
                        elif state in (win32service.SERVICE_STOP_PENDING, win32service.SERVICE_START_PENDING):
                            status = ServiceStatus.UNKNOWN
                        else:
                            status = ServiceStatus.FAILED
                        
                        # Check if service is enabled (auto-start)
                        try:
                            service_handle = win32service.OpenService(scm, service_name, win32service.SERVICE_QUERY_CONFIG)
                            config = win32service.QueryServiceConfig(service_handle)
                            enabled = config[1] in (win32service.SERVICE_AUTO_START, win32service.SERVICE_BOOT_START, win32service.SERVICE_SYSTEM_START)
                            win32service.CloseServiceHandle(service_handle)
                        except:
                            enabled = False
                        
                        service_info = ServiceInfo(
                            name=service_name,
                            status=status,
                            enabled=enabled,
                            description=display_name,
                            pid=service_status[2] if service_status[2] != 0 else None
                        )
                        services.append(service_info)
                    
                    win32service.CloseServiceHandle(scm)
                except Exception as e:
                    raise PlatformError(f"Failed to enumerate Windows services: {e}", platform="windows")
            else:
                # Fallback using sc command
                try:
                    result = subprocess.run(['sc', 'query'], capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        current_service = None
                        for line in result.stdout.split('\n'):
                            line = line.strip()
                            if line.startswith('SERVICE_NAME:'):
                                current_service = line.split(':', 1)[1].strip()
                            elif line.startswith('STATE') and current_service:
                                state_info = line.split(':', 1)[1].strip()
                                if 'RUNNING' in state_info:
                                    status = ServiceStatus.RUNNING
                                elif 'STOPPED' in state_info:
                                    status = ServiceStatus.STOPPED
                                else:
                                    status = ServiceStatus.UNKNOWN
                                
                                service_info = ServiceInfo(
                                    name=current_service,
                                    status=status,
                                    enabled=False,  # Cannot determine from sc query
                                    description=f"Windows service: {current_service}"
                                )
                                services.append(service_info)
                                current_service = None
                except subprocess.CalledProcessError:
                    pass
            
            return services
        except Exception as e:
            raise PlatformError(f"Failed to get system services: {e}", platform="windows")

    # Service Management Methods
    def install_service(self, service_config: Dict[str, Any]) -> bool:
        """Install a Windows service."""
        try:
            service_name = service_config.get('name')
            if not service_name:
                raise PlatformError("Service name is required", platform="windows")
            
            display_name = service_config.get('display_name', service_name)
            description = service_config.get('description', 'Network Monitoring Agent')
            exec_path = service_config.get('exec_start', r'C:\Program Files\NetworkAgent\network-agent.exe')
            
            if win32serviceutil is not None:
                # Use Python Windows service utilities
                try:
                    win32serviceutil.InstallService(
                        pythonClassString=service_config.get('python_class', 'NetworkAgentService'),
                        serviceName=service_name,
                        displayName=display_name,
                        description=description
                    )
                    return True
                except Exception as e:
                    raise PlatformError(f"Failed to install service using win32serviceutil: {e}", platform="windows")
            else:
                # Fallback using sc command
                try:
                    sc_cmd = [
                        'sc', 'create', service_name,
                        'binPath=', exec_path,
                        'DisplayName=', display_name,
                        'start=', 'auto'
                    ]
                    subprocess.run(sc_cmd, check=True, timeout=30)
                    
                    # Set description
                    subprocess.run(['sc', 'description', service_name, description], timeout=30)
                    
                    return True
                except subprocess.CalledProcessError as e:
                    raise PlatformError(f"Failed to install service using sc: {e}", platform="windows")
        except Exception as e:
            raise PlatformError(f"Failed to install service: {e}", platform="windows")

    def start_service(self, service_name: str) -> bool:
        """Start a Windows service."""
        try:
            if win32serviceutil is not None:
                try:
                    win32serviceutil.StartService(service_name)
                    return True
                except Exception as e:
                    raise PlatformError(f"Failed to start service using win32serviceutil: {e}", platform="windows")
            else:
                try:
                    subprocess.run(['sc', 'start', service_name], check=True, timeout=30)
                    return True
                except subprocess.CalledProcessError as e:
                    raise PlatformError(f"Failed to start service using sc: {e}", platform="windows")
        except Exception as e:
            raise PlatformError(f"Failed to start service: {e}", platform="windows")

    def stop_service(self, service_name: str) -> bool:
        """Stop a Windows service."""
        try:
            if win32serviceutil is not None:
                try:
                    win32serviceutil.StopService(service_name)
                    return True
                except Exception as e:
                    raise PlatformError(f"Failed to stop service using win32serviceutil: {e}", platform="windows")
            else:
                try:
                    subprocess.run(['sc', 'stop', service_name], check=True, timeout=30)
                    return True
                except subprocess.CalledProcessError as e:
                    raise PlatformError(f"Failed to stop service using sc: {e}", platform="windows")
        except Exception as e:
            raise PlatformError(f"Failed to stop service: {e}", platform="windows")

    def get_service_status(self, service_name: str) -> ServiceStatus:
        """Get Windows service status."""
        try:
            if win32service is not None:
                try:
                    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
                    service_handle = win32service.OpenService(scm, service_name, win32service.SERVICE_QUERY_STATUS)
                    status = win32service.QueryServiceStatus(service_handle)
                    
                    state = status[1]
                    if state == win32service.SERVICE_RUNNING:
                        return ServiceStatus.RUNNING
                    elif state == win32service.SERVICE_STOPPED:
                        return ServiceStatus.STOPPED
                    elif state in (win32service.SERVICE_STOP_PENDING, win32service.SERVICE_START_PENDING):
                        return ServiceStatus.UNKNOWN
                    else:
                        return ServiceStatus.FAILED
                        
                except Exception:
                    return ServiceStatus.UNKNOWN
                finally:
                    try:
                        win32service.CloseServiceHandle(service_handle)
                        win32service.CloseServiceHandle(scm)
                    except:
                        pass
            else:
                try:
                    result = subprocess.run(['sc', 'query', service_name], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        if 'RUNNING' in result.stdout:
                            return ServiceStatus.RUNNING
                        elif 'STOPPED' in result.stdout:
                            return ServiceStatus.STOPPED
                        else:
                            return ServiceStatus.UNKNOWN
                    else:
                        return ServiceStatus.UNKNOWN
                except:
                    return ServiceStatus.UNKNOWN
        except Exception:
            return ServiceStatus.UNKNOWN

    # Network/Tunnel Management Methods
    def create_tunnel_interface(self, config: TunnelConfig) -> bool:
        """Create a network tunnel interface on Windows."""
        try:
            if config.tunnel_type == TunnelType.WIREGUARD:
                return self._create_wireguard_tunnel(config)
            elif config.tunnel_type == TunnelType.SSH:
                return self._create_ssh_tunnel(config)
            else:
                raise PlatformError(f"Tunnel type {config.tunnel_type} not supported", platform="windows")
        except Exception as e:
            raise PlatformError(f"Failed to create tunnel: {e}", platform="windows")

    def _create_wireguard_tunnel(self, config: TunnelConfig) -> bool:
        """Create a WireGuard tunnel on Windows."""
        try:
            # Check if WireGuard is available
            wg_path = self._find_wireguard_executable()
            if not wg_path:
                raise PlatformError("WireGuard not found", platform="windows")
            
            # Create WireGuard configuration
            wg_config_dir = Path(r'C:\Program Files\WireGuard\Data\Configurations')
            wg_config_dir.mkdir(parents=True, exist_ok=True)
            
            wg_config_path = wg_config_dir / f'{config.name}.conf'
            wg_config_content = self._create_wireguard_config(config)
            
            # Write configuration file
            with open(wg_config_path, 'w') as f:
                f.write(wg_config_content)
            
            # Start the tunnel using WireGuard service
            subprocess.run([str(wg_path), '/installtunnelservice', str(wg_config_path)], 
                         check=True, timeout=30)
            
            return True
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"WireGuard tunnel creation failed: {e}", platform="windows")

    def _find_wireguard_executable(self) -> Optional[Path]:
        """Find WireGuard executable on Windows."""
        possible_paths = [
            Path(r'C:\Program Files\WireGuard\wireguard.exe'),
            Path(r'C:\Program Files (x86)\WireGuard\wireguard.exe'),
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        # Try to find in PATH
        try:
            result = subprocess.run(['where', 'wireguard'], capture_output=True, text=True)
            if result.returncode == 0:
                return Path(result.stdout.strip().split('\n')[0])
        except:
            pass
        
        return None

    def _create_wireguard_config(self, config: TunnelConfig) -> str:
        """Create WireGuard configuration content for Windows."""
        wg_config = f"""[Interface]
PrivateKey = {config.private_key}
Address = {config.local_ip}
"""
        
        if config.config_data and 'dns' in config.config_data:
            wg_config += f"DNS = {config.config_data['dns']}\n"
        
        wg_config += f"""
[Peer]
PublicKey = {config.public_key}
Endpoint = {config.endpoint}
AllowedIPs = {', '.join(config.allowed_ips or ['0.0.0.0/0'])}
"""
        
        if config.config_data and 'persistent_keepalive' in config.config_data:
            wg_config += f"PersistentKeepalive = {config.config_data['persistent_keepalive']}\n"
        
        return wg_config

    def _create_ssh_tunnel(self, config: TunnelConfig) -> bool:
        """Create an SSH tunnel on Windows."""
        try:
            # Use plink (PuTTY) or ssh if available
            ssh_executable = self._find_ssh_executable()
            if not ssh_executable:
                raise PlatformError("SSH client not found", platform="windows")
            
            ssh_command = [
                str(ssh_executable), '-N',
                '-L', f"{config.local_port}:{config.remote_ip}:{config.remote_port}",
                config.endpoint
            ]
            
            if config.private_key:
                if 'plink' in str(ssh_executable):
                    ssh_command.extend(['-i', config.private_key])
                else:
                    ssh_command.extend(['-i', config.private_key])
            
            # Start SSH tunnel in background
            subprocess.Popen(ssh_command, creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except Exception as e:
            raise PlatformError(f"SSH tunnel creation failed: {e}", platform="windows")

    def _find_ssh_executable(self) -> Optional[Path]:
        """Find SSH executable on Windows."""
        possible_paths = [
            Path(r'C:\Program Files\PuTTY\plink.exe'),
            Path(r'C:\Windows\System32\OpenSSH\ssh.exe'),
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        # Try to find in PATH
        for executable in ['ssh', 'plink']:
            try:
                result = subprocess.run(['where', executable], capture_output=True, text=True)
                if result.returncode == 0:
                    return Path(result.stdout.strip().split('\n')[0])
            except:
                continue
        
        return None

    def destroy_tunnel_interface(self, tunnel_name: str) -> bool:
        """Destroy a network tunnel interface on Windows."""
        try:
            # Try WireGuard first
            wg_path = self._find_wireguard_executable()
            if wg_path:
                try:
                    subprocess.run([str(wg_path), '/uninstalltunnelservice', tunnel_name], 
                                 check=True, timeout=30)
                    return True
                except subprocess.CalledProcessError:
                    pass
            
            # Try to kill SSH tunnels
            try:
                result = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq ssh.exe'], 
                                      capture_output=True, text=True)
                if 'ssh.exe' in result.stdout:
                    subprocess.run(['taskkill', '/F', '/IM', 'ssh.exe'], check=True)
                    return True
                
                result = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq plink.exe'], 
                                      capture_output=True, text=True)
                if 'plink.exe' in result.stdout:
                    subprocess.run(['taskkill', '/F', '/IM', 'plink.exe'], check=True)
                    return True
            except subprocess.CalledProcessError:
                pass
            
            return False
        except Exception as e:
            raise PlatformError(f"Failed to destroy tunnel: {e}", platform="windows")

    def get_active_tunnels(self) -> List[Dict[str, Any]]:
        """Get information about active tunnels on Windows."""
        try:
            tunnels = []
            
            # Check WireGuard tunnels
            wg_path = self._find_wireguard_executable()
            if wg_path:
                try:
                    result = subprocess.run([str(wg_path), '/dumplog'], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        # Parse WireGuard log for active tunnels
                        for line in result.stdout.split('\n'):
                            if 'Interface' in line and 'up' in line:
                                interface_name = line.split()[1] if len(line.split()) > 1 else 'unknown'
                                tunnels.append({
                                    'name': interface_name,
                                    'type': 'wireguard',
                                    'status': 'active'
                                })
                except subprocess.CalledProcessError:
                    pass
            
            # Check SSH tunnels
            try:
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ssh.exe'], 
                                      capture_output=True, text=True)
                if 'ssh.exe' in result.stdout:
                    for line in result.stdout.split('\n'):
                        if 'ssh.exe' in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                pid = parts[1]
                                tunnels.append({
                                    'name': f'ssh-tunnel-{pid}',
                                    'type': 'ssh',
                                    'status': 'active',
                                    'pid': int(pid)
                                })
                
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq plink.exe'], 
                                      capture_output=True, text=True)
                if 'plink.exe' in result.stdout:
                    for line in result.stdout.split('\n'):
                        if 'plink.exe' in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                pid = parts[1]
                                tunnels.append({
                                    'name': f'plink-tunnel-{pid}',
                                    'type': 'ssh',
                                    'status': 'active',
                                    'pid': int(pid)
                                })
            except subprocess.CalledProcessError:
                pass
            
            return tunnels
        except Exception as e:
            raise PlatformError(f"Failed to get active tunnels: {e}", platform="windows")

    # File System Methods
    def get_default_config_path(self) -> Path:
        """Get default configuration path for Windows."""
        return Path(r'C:\ProgramData\NetworkAgent')

    def get_default_log_path(self) -> Path:
        """Get default log path for Windows."""
        return Path(r'C:\ProgramData\NetworkAgent\logs')

    def get_service_config_path(self) -> Path:
        """Get service configuration path for Windows."""
        return Path(r'C:\ProgramData\NetworkAgent\service.yaml')

    def get_temp_path(self) -> Path:
        """Get temporary directory path for Windows."""
        return Path(os.environ.get('TEMP', r'C:\Temp'))

    # Security Methods
    def set_file_permissions(self, file_path: Path, permissions: Union[str, int]) -> bool:
        """Set file permissions on Windows."""
        try:
            # Windows permissions are more complex, this is a simplified implementation
            # In a production environment, you would use Windows ACLs
            
            if isinstance(permissions, str):
                # Convert Unix-style permissions to Windows attributes
                if permissions in ['600', '0600']:
                    # Owner read/write only - set hidden and system attributes
                    os.system(f'attrib +H +S "{file_path}"')
                elif permissions in ['644', '0644']:
                    # Owner read/write, others read - remove special attributes
                    os.system(f'attrib -H -S "{file_path}"')
                elif permissions in ['755', '0755']:
                    # Executable permissions - no special handling needed on Windows
                    pass
            
            return True
        except Exception as e:
            raise PlatformError(f"Failed to set file permissions: {e}", platform="windows")

    def create_secure_directory(self, dir_path: Path, owner: Optional[str] = None) -> bool:
        """Create a directory with secure permissions on Windows."""
        try:
            # Create directory
            dir_path.mkdir(parents=True, exist_ok=True)
            
            # Set secure permissions using icacls
            try:
                # Remove inherited permissions and grant full control to current user only
                subprocess.run([
                    'icacls', str(dir_path), 
                    '/inheritance:d', '/grant:r', f'{os.environ.get("USERNAME", "Administrator")}:F'
                ], check=True, timeout=30)
            except subprocess.CalledProcessError:
                # Fallback: just create the directory
                pass
            
            return True
        except Exception as e:
            raise PlatformError(f"Failed to create secure directory: {e}", platform="windows")

    # Firewall Methods
    def get_firewall_rules(self) -> List[Dict[str, Any]]:
        """Get Windows Firewall rules."""
        try:
            rules = []
            
            # Use netsh to get firewall rules
            result = subprocess.run([
                'netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                current_rule = {}
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line.startswith('Rule Name:'):
                        if current_rule:
                            rules.append(current_rule)
                        current_rule = {'name': line.split(':', 1)[1].strip()}
                    elif ':' in line and current_rule:
                        key, value = line.split(':', 1)
                        current_rule[key.strip().lower().replace(' ', '_')] = value.strip()
                
                if current_rule:
                    rules.append(current_rule)
            
            return rules
        except Exception as e:
            raise PlatformError(f"Failed to get firewall rules: {e}", platform="windows")

    def add_firewall_rule(self, rule_config: Dict[str, Any]) -> bool:
        """Add a Windows Firewall rule."""
        try:
            rule_name = rule_config.get('name', 'NetworkAgent Rule')
            direction = rule_config.get('direction', 'in')
            action = rule_config.get('action', 'allow')
            protocol = rule_config.get('protocol', 'TCP')
            port = rule_config.get('port')
            
            netsh_cmd = [
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                f'name={rule_name}',
                f'dir={direction}',
                f'action={action}',
                f'protocol={protocol}'
            ]
            
            if port:
                netsh_cmd.append(f'localport={port}')
            
            subprocess.run(netsh_cmd, check=True, timeout=30)
            return True
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"Failed to add firewall rule: {e}", platform="windows")

    # Command Execution Methods
    def execute_command(self, command: Union[str, List[str]], 
                       timeout: Optional[int] = None,
                       capture_output: bool = True) -> Dict[str, Any]:
        """Execute a system command on Windows."""
        try:
            if isinstance(command, str):
                # On Windows, use shell=True for string commands
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=capture_output,
                    text=True,
                    timeout=timeout
                )
            else:
                result = subprocess.run(
                    command,
                    capture_output=capture_output,
                    text=True,
                    timeout=timeout
                )
            
            return {
                'returncode': result.returncode,
                'stdout': result.stdout if capture_output else '',
                'stderr': result.stderr if capture_output else '',
                'success': result.returncode == 0
            }
        except subprocess.TimeoutExpired as e:
            raise PlatformError(f"Command timeout: {e}", platform="windows")
        except Exception as e:
            raise PlatformError(f"Command execution failed: {e}", platform="windows")

    def _check_admin_privileges(self) -> bool:
        """Check if running with administrator privileges on Windows."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False