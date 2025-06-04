"""
Linux-specific platform implementation.
"""

import os
import pwd
import grp
import stat
import subprocess
import time
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

import psutil

from platforms.base_platform import (
    BasePlatform, SystemMetrics, NetworkInterface, ProcessInfo, 
    ServiceInfo, ServiceStatus, TunnelConfig, TunnelType, PlatformError
)


class LinuxPlatform(BasePlatform):
    """Linux-specific platform implementation."""

    def __init__(self):
        super().__init__()
        self._systemd_available = self._check_systemd_available()

    def _get_platform_name(self) -> str:
        return "linux"

    def _check_systemd_available(self) -> bool:
        """Check if systemd is available on this system."""
        try:
            result = subprocess.run(['systemctl', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    # System Information Methods
    def get_system_metrics(self) -> SystemMetrics:
        """Get comprehensive system metrics for Linux."""
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
            raise PlatformError(f"Failed to get system metrics: {e}", platform="linux")

    def get_network_interfaces(self) -> List[NetworkInterface]:
        """Get network interface information for Linux."""
        try:
            interfaces = []
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            net_io_counters = psutil.net_io_counters(pernic=True)
            
            for interface_name, addresses in net_if_addrs.items():
                # Skip loopback interface
                if interface_name == 'lo':
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
            raise PlatformError(f"Failed to get network interfaces: {e}", platform="linux")

    def get_running_processes(self, limit: Optional[int] = None) -> List[ProcessInfo]:
        """Get running process information for Linux."""
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
            raise PlatformError(f"Failed to get running processes: {e}", platform="linux")

    def get_system_services(self) -> List[ServiceInfo]:
        """Get system service information for Linux."""
        try:
            services = []
            
            if self._systemd_available:
                # Use systemctl to get service information
                result = subprocess.run(
                    ['systemctl', 'list-units', '--type=service', '--all', '--no-pager', '--plain'],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                        if not line.strip():
                            continue
                        
                        parts = line.split()
                        if len(parts) >= 4:
                            service_name = parts[0].replace('.service', '')
                            load_state = parts[1]
                            active_state = parts[2]
                            sub_state = parts[3]
                            description = ' '.join(parts[4:]) if len(parts) > 4 else ""
                            
                            # Map systemd states to our ServiceStatus enum
                            if active_state == 'active' and sub_state == 'running':
                                status = ServiceStatus.RUNNING
                            elif active_state == 'inactive':
                                status = ServiceStatus.STOPPED
                            elif active_state == 'failed':
                                status = ServiceStatus.FAILED
                            else:
                                status = ServiceStatus.UNKNOWN
                            
                            service = ServiceInfo(
                                name=service_name,
                                status=status,
                                enabled=load_state == 'enabled',
                                description=description
                            )
                            services.append(service)
            else:
                # Fallback to /etc/init.d for systems without systemd
                init_d_path = Path('/etc/init.d')
                if init_d_path.exists():
                    for service_file in init_d_path.iterdir():
                        if service_file.is_file() and service_file.stat().st_mode & stat.S_IXUSR:
                            service = ServiceInfo(
                                name=service_file.name,
                                status=ServiceStatus.UNKNOWN,
                                enabled=False,
                                description=f"Init.d service: {service_file.name}"
                            )
                            services.append(service)
            
            return services
        except Exception as e:
            raise PlatformError(f"Failed to get system services: {e}", platform="linux")

    # Service Management Methods
    def install_service(self, service_config: Dict[str, Any]) -> bool:
        """Install a systemd service on Linux."""
        try:
            if not self._systemd_available:
                raise PlatformError("systemd not available", platform="linux")
            
            service_name = service_config.get('name')
            if not service_name:
                raise PlatformError("Service name is required", platform="linux")
            
            # Create systemd unit file
            unit_content = self._create_systemd_unit(service_config)
            unit_file_path = Path(f'/etc/systemd/system/{service_name}.service')
            
            # Write unit file
            with open(unit_file_path, 'w') as f:
                f.write(unit_content)
            
            # Set proper permissions
            os.chmod(unit_file_path, 0o644)
            
            # Reload systemd daemon
            subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=30)
            
            # Enable service if requested
            if service_config.get('enabled', True):
                subprocess.run(['systemctl', 'enable', service_name], check=True, timeout=30)
            
            return True
        except Exception as e:
            raise PlatformError(f"Failed to install service: {e}", platform="linux")

    def _create_systemd_unit(self, config: Dict[str, Any]) -> str:
        """Create systemd unit file content."""
        name = config.get('name', 'network-agent')
        description = config.get('description', 'Network Monitoring Agent')
        exec_start = config.get('exec_start', '/usr/local/bin/network-agent')
        user = config.get('user', 'network-agent')
        group = config.get('group', 'network-agent')
        working_directory = config.get('working_directory', '/opt/network-agent')
        environment = config.get('environment', {})
        
        unit_content = f"""[Unit]
Description={description}
After=network.target
Wants=network.target

[Service]
Type=simple
User={user}
Group={group}
WorkingDirectory={working_directory}
ExecStart={exec_start}
Restart=always
RestartSec=10
"""
        
        # Add environment variables
        for key, value in environment.items():
            unit_content += f"Environment={key}={value}\n"
        
        unit_content += """
[Install]
WantedBy=multi-user.target
"""
        
        return unit_content

    def start_service(self, service_name: str) -> bool:
        """Start a systemd service."""
        try:
            if not self._systemd_available:
                raise PlatformError("systemd not available", platform="linux")
            
            subprocess.run(['systemctl', 'start', service_name], check=True, timeout=30)
            return True
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"Failed to start service {service_name}: {e}", platform="linux")

    def stop_service(self, service_name: str) -> bool:
        """Stop a systemd service."""
        try:
            if not self._systemd_available:
                raise PlatformError("systemd not available", platform="linux")
            
            subprocess.run(['systemctl', 'stop', service_name], check=True, timeout=30)
            return True
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"Failed to stop service {service_name}: {e}", platform="linux")

    def get_service_status(self, service_name: str) -> ServiceStatus:
        """Get systemd service status."""
        try:
            if not self._systemd_available:
                return ServiceStatus.UNKNOWN
            
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True, text=True, timeout=10
            )
            
            status_output = result.stdout.strip()
            
            if status_output == 'active':
                return ServiceStatus.RUNNING
            elif status_output == 'inactive':
                return ServiceStatus.STOPPED
            elif status_output == 'failed':
                return ServiceStatus.FAILED
            else:
                return ServiceStatus.UNKNOWN
        except Exception:
            return ServiceStatus.UNKNOWN

    # Network/Tunnel Management Methods
    def create_tunnel_interface(self, config: TunnelConfig) -> bool:
        """Create a network tunnel interface on Linux."""
        try:
            if config.tunnel_type == TunnelType.WIREGUARD:
                return self._create_wireguard_tunnel(config)
            elif config.tunnel_type == TunnelType.SSH:
                return self._create_ssh_tunnel(config)
            else:
                raise PlatformError(f"Tunnel type {config.tunnel_type} not supported", platform="linux")
        except Exception as e:
            raise PlatformError(f"Failed to create tunnel: {e}", platform="linux")

    def _create_wireguard_tunnel(self, config: TunnelConfig) -> bool:
        """Create a WireGuard tunnel on Linux."""
        try:
            # Check if WireGuard is available
            subprocess.run(['which', 'wg'], check=True, capture_output=True)
            
            # Create WireGuard configuration
            wg_config_path = Path(f'/etc/wireguard/{config.name}.conf')
            wg_config_content = self._create_wireguard_config(config)
            
            # Write configuration file
            with open(wg_config_path, 'w') as f:
                f.write(wg_config_content)
            
            # Set secure permissions
            os.chmod(wg_config_path, 0o600)
            
            # Bring up the interface
            subprocess.run(['wg-quick', 'up', config.name], check=True, timeout=30)
            
            return True
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"WireGuard tunnel creation failed: {e}", platform="linux")

    def _create_wireguard_config(self, config: TunnelConfig) -> str:
        """Create WireGuard configuration content."""
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
        """Create an SSH tunnel on Linux."""
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
            raise PlatformError(f"SSH tunnel creation failed: {e}", platform="linux")

    def destroy_tunnel_interface(self, tunnel_name: str) -> bool:
        """Destroy a network tunnel interface."""
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
            raise PlatformError(f"Failed to destroy tunnel: {e}", platform="linux")

    def get_active_tunnels(self) -> List[Dict[str, Any]]:
        """Get information about active tunnels."""
        try:
            tunnels = []
            
            # Check WireGuard tunnels
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
            raise PlatformError(f"Failed to get active tunnels: {e}", platform="linux")

    # File System Methods
    def get_default_config_path(self) -> Path:
        """Get default configuration path for Linux."""
        return Path('/etc/network-agent')

    def get_default_log_path(self) -> Path:
        """Get default log path for Linux."""
        return Path('/var/log/network-agent')

    def get_service_config_path(self) -> Path:
        """Get service configuration path for Linux."""
        return Path('/etc/systemd/system/network-agent.service')

    def get_temp_path(self) -> Path:
        """Get temporary directory path for Linux."""
        return Path('/tmp')

    # Security Methods
    def set_file_permissions(self, file_path: Path, permissions: Union[str, int]) -> bool:
        """Set file permissions on Linux."""
        try:
            if isinstance(permissions, str):
                # Convert string permissions like "600" to octal
                permissions = int(permissions, 8)
            
            os.chmod(file_path, permissions)
            return True
        except Exception as e:
            raise PlatformError(f"Failed to set file permissions: {e}", platform="linux")

    def create_secure_directory(self, dir_path: Path, owner: Optional[str] = None) -> bool:
        """Create a directory with secure permissions on Linux."""
        try:
            # Create directory with secure permissions (700)
            dir_path.mkdir(parents=True, exist_ok=True, mode=0o700)
            
            # Set owner if specified
            if owner:
                try:
                    user_info = pwd.getpwnam(owner)
                    os.chown(dir_path, user_info.pw_uid, user_info.pw_gid)
                except KeyError:
                    raise PlatformError(f"User {owner} not found", platform="linux")
            
            return True
        except Exception as e:
            raise PlatformError(f"Failed to create secure directory: {e}", platform="linux")

    # Firewall Methods
    def get_firewall_rules(self) -> List[Dict[str, Any]]:
        """Get iptables firewall rules."""
        try:
            rules = []
            
            # Get iptables rules
            result = subprocess.run(['iptables', '-L', '-n', '--line-numbers'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                current_chain = None
                for line in result.stdout.split('\n'):
                    if line.startswith('Chain'):
                        current_chain = line.split()[1]
                    elif line and not line.startswith('num') and current_chain:
                        parts = line.split()
                        if len(parts) >= 3:
                            rules.append({
                                'chain': current_chain,
                                'line_number': parts[0] if parts[0].isdigit() else None,
                                'target': parts[1] if len(parts) > 1 else '',
                                'protocol': parts[2] if len(parts) > 2 else '',
                                'source': parts[3] if len(parts) > 3 else '',
                                'destination': parts[4] if len(parts) > 4 else '',
                                'raw_rule': line
                            })
            
            return rules
        except Exception as e:
            raise PlatformError(f"Failed to get firewall rules: {e}", platform="linux")

    def add_firewall_rule(self, rule_config: Dict[str, Any]) -> bool:
        """Add an iptables firewall rule."""
        try:
            chain = rule_config.get('chain', 'INPUT')
            target = rule_config.get('target', 'ACCEPT')
            protocol = rule_config.get('protocol')
            port = rule_config.get('port')
            source = rule_config.get('source')
            
            iptables_cmd = ['iptables', '-A', chain, '-j', target]
            
            if protocol:
                iptables_cmd.extend(['-p', protocol])
            
            if port:
                iptables_cmd.extend(['--dport', str(port)])
            
            if source:
                iptables_cmd.extend(['-s', source])
            
            subprocess.run(iptables_cmd, check=True, timeout=30)
            return True
        except subprocess.CalledProcessError as e:
            raise PlatformError(f"Failed to add firewall rule: {e}", platform="linux")

    # Command Execution Methods
    def execute_command(self, command: Union[str, List[str]], 
                       timeout: Optional[int] = None,
                       capture_output: bool = True) -> Dict[str, Any]:
        """Execute a system command on Linux."""
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
            raise PlatformError(f"Command timeout: {e}", platform="linux")
        except Exception as e:
            raise PlatformError(f"Command execution failed: {e}", platform="linux")

    def _check_admin_privileges(self) -> bool:
        """Check if running with root privileges on Linux."""
        return os.geteuid() == 0