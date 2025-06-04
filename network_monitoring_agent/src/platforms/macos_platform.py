"""
macOS-specific platform implementation.
"""

import os
import pwd
import grp
import stat
import subprocess
import time
import json
import plistlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

import psutil

from platforms.base_platform import (
    BasePlatform, SystemMetrics, NetworkInterface, ProcessInfo, 
    ServiceInfo, ServiceStatus, TunnelConfig, TunnelType, PlatformError
)


class MacOSPlatform(BasePlatform):
    """macOS-specific platform implementation."""

    def __init__(self):
        super().__init__()
        self._launchd_available = self._check_launchd_available()

    def _get_platform_name(self) -> str:
        return "macos"

    def _check_launchd_available(self) -> bool:
        """Check if launchd is available (should always be true on macOS)."""
        try:
            result = subprocess.run(['launchctl', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    # System Information Methods
    def get_system_metrics(self) -> SystemMetrics:
        """Get comprehensive system metrics for macOS."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics (root filesystem)
            disk = psutil.disk_usage('/')
            
            # Load average
            load_avg = list(os.getloadavg())
            
            # Uptime and boot time
            boot_time = int(psutil.boot_time())
            uptime = int(time.time() - boot_time)
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_total=memory.total,
                memory_used=memory.used,
                disk_percent=disk.percent,
                disk_total=disk.total,
                disk_used=disk.used,
                load_average=load_avg,
                uptime=uptime,
                boot_time=boot_time
            )
        except Exception as e:
            raise PlatformError(f"Failed to get system metrics: {e}", platform="macos")

    def get_network_interfaces(self) -> List[NetworkInterface]:
        """Get network interface information for macOS."""
        try:
            interfaces = []
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            net_io_counters = psutil.net_io_counters(pernic=True)
            
            for interface_name, addresses in net_if_addrs.items():
                # Skip loopback interface
                if interface_name == 'lo0':
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
            raise PlatformError(f"Failed to get network interfaces: {e}", platform="macos")

    def get_running_processes(self, limit: Optional[int] = None) -> List[ProcessInfo]:
        """Get running process information for macOS."""
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
            raise PlatformError(f"Failed to get running processes: {e}", platform="macos")

    def get_system_services(self) -> List[ServiceInfo]:
        """Get system service information for macOS."""
        try:
            services = []
            
            if self._launchd_available:
                # Use launchctl to get service information
                result = subprocess.run(
                    ['launchctl', 'list'],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                        if not line.strip():
                            continue
                        
                        parts = line.split('\t')
                        if len(parts) >= 3:
                            pid = parts[0] if parts[0] != '-' else None
                            exit_code = parts[1] if parts[1] != '-' else None
                            service_name = parts[2]
                            
                            # Determine service status
                            if pid and pid != '-':
                                status = ServiceStatus.RUNNING
                            elif exit_code == '0':
                                status = ServiceStatus.STOPPED
                            elif exit_code and exit_code != '0':
                                status = ServiceStatus.FAILED
                            else:
                                status = ServiceStatus.UNKNOWN
                            
                            # Check if service is enabled (loaded)
                            enabled = True  # If it's in the list, it's loaded
                            
                            service = ServiceInfo(
                                name=service_name,
                                status=status,
                                enabled=enabled,
                                description=f"launchd service: {service_name}",
                                pid=int(pid) if pid and pid != '-' else None
                            )
                            services.append(service)
            
            return services
        except Exception as e:
            raise PlatformError(f"Failed to get system services: {e}", platform="macos")

    # Service Management Methods
    def install_service(self, service_config: Dict[str, Any]) -> bool:
        """Install a launchd service on macOS."""
        try:
            if not self._launchd_available:
                raise PlatformError("launchd not available", platform="macos")
            
            service_name = service_config.get('name')
            if not service_name:
                raise PlatformError("Service name is required", platform="macos")
            
            # Create launchd plist
            plist_content = self._create_launchd_plist(service_config)
            plist_file_path = Path(f'/Library/LaunchDaemons/com.company.{service_name}.plist')
            
            # Write plist file
            with open(plist_file_path, 'wb') as f:
                plistlib.dump(plist_content, f)
            
            # Set proper permissions
            os.chmod(plist_file_path, 0o644)
            os.chown(plist_file_path, 0, 0)  # root:wheel
            
            # Load service if requested
            if service_config.get('enabled', True):
                subprocess.run(['launchctl', 'load', str(plist_file_path)], check=True, timeout=30)
            
            return True
        except Exception as e:
            raise PlatformError(f"Failed to install service: {e}", platform="macos")

    def _create_launchd_plist(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create launchd plist content."""
        name = config.get('name', 'network-agent')
        description = config.get('description', 'Network Monitoring Agent')
        exec_start = config.get('exec_start', '/usr/local/bin/network-agent')
        working_directory = config.get('working_directory', '/usr/local/etc/network-agent')
        user = config.get('user', 'root')
        group = config.get('group', 'wheel')
        environment = config.get('environment', {})
        
        plist_content = {
            'Label': f'com.company.{name}',
            'ProgramArguments': exec_start.split() if isinstance(exec_start, str) else exec_start,
            'RunAtLoad': True,
            'KeepAlive': True,
            'WorkingDirectory': working_directory,
            'UserName': user,
            'GroupName': group,
            'StandardOutPath': f'/usr/local/var/log/{name}/stdout.log',
            'StandardErrorPath': f'/usr/local/var/log/{name}/stderr.log'
        }
        
        # Add environment variables
        if environment:
            plist_content['EnvironmentVariables'] = environment
        
        return plist_content

    def start_service(self, service_name: str) -> bool:
        """Start a launchd service."""
        try:
            if not self._launchd_available:
                raise PlatformError("launchd not available", platform="macos")
            
            # Try to start by service name first
            result = subprocess.run(['launchctl', 'start', service_name], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return True
            
            # If that fails, try to load the plist file
            plist_path = Path(f'/Library/LaunchDaemons/{service_name}.plist')
            if plist_path.exists():
                subprocess.run(['launchctl', 'load', str(plist_path)], check=True, timeout=30)
                return True
            
            return False
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"Failed to start service {service_name}: {e}", platform="macos")

    def stop_service(self, service_name: str) -> bool:
        """Stop a launchd service."""
        try:
            if not self._launchd_available:
                raise PlatformError("launchd not available", platform="macos")
            
            # Try to stop by service name first
            result = subprocess.run(['launchctl', 'stop', service_name], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return True
            
            # If that fails, try to unload the plist file
            plist_path = Path(f'/Library/LaunchDaemons/{service_name}.plist')
            if plist_path.exists():
                subprocess.run(['launchctl', 'unload', str(plist_path)], check=True, timeout=30)
                return True
            
            return False
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"Failed to stop service {service_name}: {e}", platform="macos")

    def get_service_status(self, service_name: str) -> ServiceStatus:
        """Get launchd service status."""
        try:
            if not self._launchd_available:
                return ServiceStatus.UNKNOWN
            
            result = subprocess.run(
                ['launchctl', 'list', service_name],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                # Parse the output to determine status
                output = result.stdout.strip()
                if '"PID"' in output and '"PID" = ' in output:
                    # Service is running
                    return ServiceStatus.RUNNING
                elif '"LastExitStatus"' in output:
                    # Service has exited
                    if '"LastExitStatus" = 0' in output:
                        return ServiceStatus.STOPPED
                    else:
                        return ServiceStatus.FAILED
                else:
                    return ServiceStatus.UNKNOWN
            else:
                return ServiceStatus.UNKNOWN
        except Exception:
            return ServiceStatus.UNKNOWN

    # Network/Tunnel Management Methods
    def create_tunnel_interface(self, config: TunnelConfig) -> bool:
        """Create a network tunnel interface on macOS."""
        try:
            if config.tunnel_type == TunnelType.WIREGUARD:
                return self._create_wireguard_tunnel(config)
            elif config.tunnel_type == TunnelType.SSH:
                return self._create_ssh_tunnel(config)
            else:
                raise PlatformError(f"Tunnel type {config.tunnel_type} not supported", platform="macos")
        except Exception as e:
            raise PlatformError(f"Failed to create tunnel: {e}", platform="macos")

    def _create_wireguard_tunnel(self, config: TunnelConfig) -> bool:
        """Create a WireGuard tunnel on macOS."""
        try:
            # Check if WireGuard is available
            wg_path = self._find_wireguard_executable()
            if not wg_path:
                raise PlatformError("WireGuard not found", platform="macos")
            
            # Create WireGuard configuration
            wg_config_dir = Path('/usr/local/etc/wireguard')
            wg_config_dir.mkdir(parents=True, exist_ok=True)
            
            wg_config_path = wg_config_dir / f'{config.name}.conf'
            wg_config_content = self._create_wireguard_config(config)
            
            # Write configuration file
            with open(wg_config_path, 'w') as f:
                f.write(wg_config_content)
            
            # Set secure permissions
            os.chmod(wg_config_path, 0o600)
            
            # Bring up the interface
            subprocess.run(['wg-quick', 'up', str(wg_config_path)], check=True, timeout=30)
            
            return True
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"WireGuard tunnel creation failed: {e}", platform="macos")

    def _find_wireguard_executable(self) -> Optional[Path]:
        """Find WireGuard executable on macOS."""
        possible_paths = [
            Path('/usr/local/bin/wg'),
            Path('/opt/homebrew/bin/wg'),
            Path('/Applications/WireGuard.app/Contents/MacOS/WireGuard'),
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        # Try to find in PATH
        try:
            result = subprocess.run(['which', 'wg'], capture_output=True, text=True)
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except:
            pass
        
        return None

    def _create_wireguard_config(self, config: TunnelConfig) -> str:
        """Create WireGuard configuration content for macOS."""
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
        """Create an SSH tunnel on macOS."""
        try:
            ssh_command = [
                'ssh', '-N', '-f',
                '-L', f"{config.local_port}:{config.remote_ip}:{config.remote_port}",
                config.endpoint
            ]
            
            if config.private_key:
                ssh_command.extend(['-i', config.private_key])
            
            subprocess.run(ssh_command, check=True, timeout=30)
            return True
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"SSH tunnel creation failed: {e}", platform="macos")

    def destroy_tunnel_interface(self, tunnel_name: str) -> bool:
        """Destroy a network tunnel interface on macOS."""
        try:
            # Try WireGuard first
            try:
                subprocess.run(['wg-quick', 'down', tunnel_name], check=True, timeout=30)
                return True
            except subprocess.CalledProcessError:
                pass
            
            # Try to kill SSH tunnels
            try:
                result = subprocess.run(['pgrep', '-f', f'ssh.*{tunnel_name}'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid:
                            subprocess.run(['kill', pid], check=True)
                    return True
            except subprocess.CalledProcessError:
                pass
            
            return False
        except Exception as e:
            raise PlatformError(f"Failed to destroy tunnel: {e}", platform="macos")

    def get_active_tunnels(self) -> List[Dict[str, Any]]:
        """Get information about active tunnels on macOS."""
        try:
            tunnels = []
            
            # Check WireGuard tunnels
            wg_path = self._find_wireguard_executable()
            if wg_path:
                try:
                    result = subprocess.run(['wg', 'show'], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        current_interface = None
                        for line in result.stdout.split('\n'):
                            if line.startswith('interface:'):
                                current_interface = line.split(':')[1].strip()
                                tunnels.append({
                                    'name': current_interface,
                                    'type': 'wireguard',
                                    'status': 'active'
                                })
                except subprocess.CalledProcessError:
                    pass
            
            # Check SSH tunnels
            try:
                result = subprocess.run(['pgrep', '-f', 'ssh.*-L'], capture_output=True, text=True)
                if result.returncode == 0:
                    ssh_pids = result.stdout.strip().split('\n')
                    for pid in ssh_pids:
                        if pid:
                            tunnels.append({
                                'name': f'ssh-tunnel-{pid}',
                                'type': 'ssh',
                                'status': 'active',
                                'pid': int(pid)
                            })
            except subprocess.CalledProcessError:
                pass
            
            return tunnels
        except Exception as e:
            raise PlatformError(f"Failed to get active tunnels: {e}", platform="macos")

    # File System Methods
    def get_default_config_path(self) -> Path:
        """Get default configuration path for macOS."""
        return Path('/usr/local/etc/network-agent')

    def get_default_log_path(self) -> Path:
        """Get default log path for macOS."""
        return Path('/usr/local/var/log/network-agent')

    def get_service_config_path(self) -> Path:
        """Get service configuration path for macOS."""
        return Path('/Library/LaunchDaemons/com.company.networkagent.plist')

    def get_temp_path(self) -> Path:
        """Get temporary directory path for macOS."""
        return Path('/tmp')

    # Security Methods
    def set_file_permissions(self, file_path: Path, permissions: Union[str, int]) -> bool:
        """Set file permissions on macOS."""
        try:
            if isinstance(permissions, str):
                # Convert string permissions like "600" to octal
                permissions = int(permissions, 8)
            
            os.chmod(file_path, permissions)
            return True
        except Exception as e:
            raise PlatformError(f"Failed to set file permissions: {e}", platform="macos")

    def create_secure_directory(self, dir_path: Path, owner: Optional[str] = None) -> bool:
        """Create a directory with secure permissions on macOS."""
        try:
            # Create directory with secure permissions (700)
            dir_path.mkdir(parents=True, exist_ok=True, mode=0o700)
            
            # Set owner if specified
            if owner:
                try:
                    user_info = pwd.getpwnam(owner)
                    os.chown(dir_path, user_info.pw_uid, user_info.pw_gid)
                except KeyError:
                    raise PlatformError(f"User {owner} not found", platform="macos")
            
            return True
        except Exception as e:
            raise PlatformError(f"Failed to create secure directory: {e}", platform="macos")

    # Firewall Methods
    def get_firewall_rules(self) -> List[Dict[str, Any]]:
        """Get pfctl firewall rules on macOS."""
        try:
            rules = []
            
            # Get pfctl rules
            result = subprocess.run(['pfctl', '-sr'], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                for i, line in enumerate(result.stdout.split('\n')):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        rules.append({
                            'line_number': i + 1,
                            'rule': line,
                            'type': 'pfctl'
                        })
            
            return rules
        except Exception as e:
            raise PlatformError(f"Failed to get firewall rules: {e}", platform="macos")

    def add_firewall_rule(self, rule_config: Dict[str, Any]) -> bool:
        """Add a pfctl firewall rule on macOS."""
        try:
            action = rule_config.get('action', 'pass')
            direction = rule_config.get('direction', 'in')
            protocol = rule_config.get('protocol', 'tcp')
            port = rule_config.get('port')
            interface = rule_config.get('interface', 'any')
            
            # Create pfctl rule
            rule = f"{action} {direction} on {interface} proto {protocol}"
            
            if port:
                rule += f" port {port}"
            
            # Add rule to pfctl (this is a simplified implementation)
            # In production, you would typically add rules to /etc/pf.conf
            # and reload the configuration
            
            # For now, just validate the rule syntax
            result = subprocess.run(['pfctl', '-nf', '-'], 
                                  input=rule, text=True, capture_output=True, timeout=30)
            
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"Failed to add firewall rule: {e}", platform="macos")

    # Command Execution Methods
    def execute_command(self, command: Union[str, List[str]], 
                       timeout: Optional[int] = None,
                       capture_output: bool = True) -> Dict[str, Any]:
        """Execute a system command on macOS."""
        try:
            if isinstance(command, str):
                command = command.split()
            
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
            raise PlatformError(f"Command timeout: {e}", platform="macos")
        except Exception as e:
            raise PlatformError(f"Command execution failed: {e}", platform="macos")

    def _check_admin_privileges(self) -> bool:
        """Check if running with root privileges on macOS."""
        return os.geteuid() == 0