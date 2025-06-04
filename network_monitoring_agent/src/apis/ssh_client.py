"""
SSH client for remote device monitoring and command execution.
"""

import asyncio
import logging
import io
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass

try:
    import paramiko
    import asyncssh
    ASYNCSSH_AVAILABLE = True
except ImportError:
    ASYNCSSH_AVAILABLE = False
    # Mock classes for when asyncssh/paramiko is not available
    class SSHClientSession: pass
    class SSHClientConnection: pass


@dataclass
class SSHConfig:
    """SSH configuration parameters."""
    host: str
    port: int = 22
    username: str = None
    password: Optional[str] = None
    private_key: Optional[str] = None
    private_key_path: Optional[Path] = None
    timeout: int = 30
    keepalive_interval: int = 60
    compression: bool = False
    known_hosts: Optional[str] = None
    host_key_checking: bool = True


class SSHError(Exception):
    """SSH-related error."""
    pass


class SSHClient:
    """
    Asynchronous SSH client for remote device monitoring.
    
    Supports password and key-based authentication, command execution,
    file transfer, and persistent connections.
    """
    
    def __init__(self):
        """Initialize SSH client."""
        self.logger = logging.getLogger(__name__)
        self.config: Optional[SSHConfig] = None
        self.connection: Optional[Any] = None
        self.is_connected = False
        
        if not ASYNCSSH_AVAILABLE:
            self.logger.warning("asyncssh not available, SSH functionality disabled")
    
    async def connect(self, host: str, username: str, password: str = None,
                     private_key: str = None, private_key_path: Path = None,
                     port: int = 22, timeout: int = 30,
                     known_hosts: str = None, host_key_checking: bool = True) -> bool:
        """
        Connect to SSH server.
        
        Args:
            host: Target host IP or hostname
            username: SSH username
            password: SSH password (if using password auth)
            private_key: Private key content as string
            private_key_path: Path to private key file
            port: SSH port (default 22)
            timeout: Connection timeout in seconds
            known_hosts: Path to known_hosts file
            host_key_checking: Whether to verify host keys
            
        Returns:
            bool: True if connection successful
            
        Raises:
            SSHError: If connection fails
        """
        if not ASYNCSSH_AVAILABLE:
            raise SSHError("asyncssh not available")
        
        try:
            self.config = SSHConfig(
                host=host,
                port=port,
                username=username,
                password=password,
                private_key=private_key,
                private_key_path=private_key_path,
                timeout=timeout,
                known_hosts=known_hosts,
                host_key_checking=host_key_checking
            )
            
            # Prepare connection options
            connect_options = {
                'host': host,
                'port': port,
                'username': username,
                'connect_timeout': timeout,
                'keepalive_interval': 60
            }
            
            # Authentication
            if password:
                connect_options['password'] = password
            elif private_key:
                # Load private key from string
                key_data = io.StringIO(private_key)
                connect_options['client_keys'] = [key_data]
            elif private_key_path and private_key_path.exists():
                connect_options['client_keys'] = [str(private_key_path)]
            else:
                raise SSHError("No authentication method provided")
            
            # Host key verification
            if not host_key_checking:
                connect_options['known_hosts'] = None
            elif known_hosts:
                connect_options['known_hosts'] = known_hosts
            
            # Establish connection
            self.connection = await asyncssh.connect(**connect_options)
            self.is_connected = True
            
            self.logger.info(f"Connected to SSH server {host}:{port}")
            return True
            
        except Exception as e:
            self.logger.error(f"SSH connection failed: {e}")
            raise SSHError(f"Connection failed: {e}")
    
    async def disconnect(self):
        """Disconnect from SSH server."""
        if self.connection:
            self.connection.close()
            await self.connection.wait_closed()
            self.connection = None
        
        self.is_connected = False
        self.config = None
        self.logger.info("Disconnected from SSH server")
    
    async def execute_command(self, command: str, timeout: int = None,
                            capture_output: bool = True,
                            check_exit_code: bool = False) -> Union[str, Tuple[str, str, int]]:
        """
        Execute a command on the remote server.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            capture_output: Whether to capture stdout/stderr
            check_exit_code: Whether to check exit code
            
        Returns:
            str: Command output (if capture_output=True and check_exit_code=False)
            Tuple[str, str, int]: (stdout, stderr, exit_code) if check_exit_code=True
            
        Raises:
            SSHError: If command execution fails
        """
        if not self.is_connected:
            raise SSHError("Not connected to SSH server")
        
        try:
            timeout = timeout or self.config.timeout
            
            result = await self.connection.run(
                command,
                timeout=timeout,
                check=False  # Don't raise exception on non-zero exit
            )
            
            stdout = result.stdout if result.stdout else ""
            stderr = result.stderr if result.stderr else ""
            exit_code = result.exit_status
            
            if check_exit_code:
                return stdout, stderr, exit_code
            elif capture_output:
                return stdout
            else:
                return ""
                
        except asyncio.TimeoutError:
            raise SSHError(f"Command timeout after {timeout} seconds")
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
            raise SSHError(f"Command execution failed: {e}")
    
    async def execute_commands(self, commands: List[str], timeout: int = None,
                             stop_on_error: bool = False) -> List[Dict[str, Any]]:
        """
        Execute multiple commands sequentially.
        
        Args:
            commands: List of commands to execute
            timeout: Timeout per command
            stop_on_error: Whether to stop on first error
            
        Returns:
            List[Dict[str, Any]]: List of command results
            
        Raises:
            SSHError: If execution fails
        """
        results = []
        
        for i, command in enumerate(commands):
            try:
                stdout, stderr, exit_code = await self.execute_command(
                    command, timeout=timeout, check_exit_code=True
                )
                
                result = {
                    'command': command,
                    'stdout': stdout,
                    'stderr': stderr,
                    'exit_code': exit_code,
                    'success': exit_code == 0,
                    'index': i
                }
                
                results.append(result)
                
                if stop_on_error and exit_code != 0:
                    break
                    
            except Exception as e:
                result = {
                    'command': command,
                    'stdout': '',
                    'stderr': str(e),
                    'exit_code': -1,
                    'success': False,
                    'index': i,
                    'error': str(e)
                }
                
                results.append(result)
                
                if stop_on_error:
                    break
        
        return results
    
    async def upload_file(self, local_path: Union[str, Path], remote_path: str,
                         preserve_attrs: bool = True) -> bool:
        """
        Upload a file to the remote server.
        
        Args:
            local_path: Local file path
            remote_path: Remote file path
            preserve_attrs: Whether to preserve file attributes
            
        Returns:
            bool: True if upload successful
            
        Raises:
            SSHError: If upload fails
        """
        if not self.is_connected:
            raise SSHError("Not connected to SSH server")
        
        try:
            local_path = Path(local_path)
            if not local_path.exists():
                raise SSHError(f"Local file not found: {local_path}")
            
            await asyncssh.scp(
                str(local_path),
                (self.connection, remote_path),
                preserve=preserve_attrs
            )
            
            self.logger.info(f"File uploaded: {local_path} -> {remote_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"File upload failed: {e}")
            raise SSHError(f"Upload failed: {e}")
    
    async def download_file(self, remote_path: str, local_path: Union[str, Path],
                           preserve_attrs: bool = True) -> bool:
        """
        Download a file from the remote server.
        
        Args:
            remote_path: Remote file path
            local_path: Local file path
            preserve_attrs: Whether to preserve file attributes
            
        Returns:
            bool: True if download successful
            
        Raises:
            SSHError: If download fails
        """
        if not self.is_connected:
            raise SSHError("Not connected to SSH server")
        
        try:
            local_path = Path(local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            await asyncssh.scp(
                (self.connection, remote_path),
                str(local_path),
                preserve=preserve_attrs
            )
            
            self.logger.info(f"File downloaded: {remote_path} -> {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"File download failed: {e}")
            raise SSHError(f"Download failed: {e}")
    
    async def create_tunnel(self, local_port: int, remote_host: str, remote_port: int,
                           bind_address: str = 'localhost') -> bool:
        """
        Create SSH port forwarding tunnel.
        
        Args:
            local_port: Local port to bind
            remote_host: Remote host to connect to
            remote_port: Remote port to connect to
            bind_address: Local address to bind to
            
        Returns:
            bool: True if tunnel created successfully
            
        Raises:
            SSHError: If tunnel creation fails
        """
        if not self.is_connected:
            raise SSHError("Not connected to SSH server")
        
        try:
            listener = await self.connection.forward_local_port(
                bind_address, local_port, remote_host, remote_port
            )
            
            self.logger.info(f"SSH tunnel created: {bind_address}:{local_port} -> {remote_host}:{remote_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"SSH tunnel creation failed: {e}")
            raise SSHError(f"Tunnel creation failed: {e}")
    
    async def get_system_info(self) -> Dict[str, str]:
        """Get basic system information from remote host."""
        commands = {
            'hostname': 'hostname',
            'uname': 'uname -a',
            'uptime': 'uptime',
            'whoami': 'whoami',
            'pwd': 'pwd',
            'date': 'date',
            'kernel': 'uname -r',
            'architecture': 'uname -m',
            'os_release': 'cat /etc/os-release 2>/dev/null || cat /etc/redhat-release 2>/dev/null || echo "Unknown"'
        }
        
        info = {}
        for key, command in commands.items():
            try:
                output = await self.execute_command(command, timeout=10)
                info[key] = output.strip()
            except Exception as e:
                info[key] = f"Error: {e}"
        
        return info
    
    async def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information and usage."""
        try:
            # CPU info
            cpu_info_output = await self.execute_command("cat /proc/cpuinfo | grep 'model name' | head -1")
            cpu_count_output = await self.execute_command("nproc")
            cpu_usage_output = await self.execute_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
            load_avg_output = await self.execute_command("uptime | awk -F'load average:' '{print $2}'")
            
            cpu_info = {
                'model': cpu_info_output.split(':')[1].strip() if ':' in cpu_info_output else 'Unknown',
                'count': int(cpu_count_output.strip()) if cpu_count_output.strip().isdigit() else 0,
                'usage_percent': float(cpu_usage_output.strip()) if cpu_usage_output.strip().replace('.', '').isdigit() else 0.0,
                'load_average': load_avg_output.strip() if load_avg_output else 'Unknown'
            }
            
            return cpu_info
            
        except Exception as e:
            self.logger.error(f"Failed to get CPU info: {e}")
            return {'error': str(e)}
    
    async def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information and usage."""
        try:
            # Memory info
            mem_output = await self.execute_command("free -m")
            
            lines = mem_output.strip().split('\n')
            if len(lines) >= 2:
                mem_line = lines[1].split()
                if len(mem_line) >= 3:
                    total = int(mem_line[1])
                    used = int(mem_line[2])
                    available = int(mem_line[6]) if len(mem_line) > 6 else total - used
                    
                    memory_info = {
                        'total_mb': total,
                        'used_mb': used,
                        'available_mb': available,
                        'usage_percent': (used / total) * 100 if total > 0 else 0
                    }
                    
                    return memory_info
            
            return {'error': 'Unable to parse memory information'}
            
        except Exception as e:
            self.logger.error(f"Failed to get memory info: {e}")
            return {'error': str(e)}
    
    async def get_disk_info(self) -> Dict[str, Any]:
        """Get disk information and usage."""
        try:
            # Disk usage
            disk_output = await self.execute_command("df -h /")
            
            lines = disk_output.strip().split('\n')
            if len(lines) >= 2:
                disk_line = lines[1].split()
                if len(disk_line) >= 5:
                    disk_info = {
                        'filesystem': disk_line[0],
                        'size': disk_line[1],
                        'used': disk_line[2],
                        'available': disk_line[3],
                        'usage_percent': float(disk_line[4].rstrip('%')) if disk_line[4].rstrip('%').replace('.', '').isdigit() else 0.0,
                        'mount_point': disk_line[5] if len(disk_line) > 5 else '/'
                    }
                    
                    return disk_info
            
            return {'error': 'Unable to parse disk information'}
            
        except Exception as e:
            self.logger.error(f"Failed to get disk info: {e}")
            return {'error': str(e)}
    
    async def get_network_info(self) -> Dict[str, Any]:
        """Get network interface information."""
        try:
            # Network interfaces
            interfaces_output = await self.execute_command("ip addr show")
            
            # Parse interface information
            interfaces = {}
            current_interface = None
            
            for line in interfaces_output.split('\n'):
                line = line.strip()
                
                # Interface line
                if line and line[0].isdigit() and ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        current_interface = parts[1].strip()
                        interfaces[current_interface] = {
                            'name': current_interface,
                            'addresses': [],
                            'status': 'UP' if 'UP' in line else 'DOWN'
                        }
                
                # IP address line
                elif line.startswith('inet ') and current_interface:
                    addr_part = line.split()[1]
                    if '/' in addr_part:
                        ip_addr = addr_part.split('/')[0]
                        interfaces[current_interface]['addresses'].append(ip_addr)
            
            return {'interfaces': interfaces}
            
        except Exception as e:
            self.logger.error(f"Failed to get network info: {e}")
            return {'error': str(e)}
    
    async def get_process_list(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get list of running processes."""
        try:
            # Get process list
            ps_output = await self.execute_command(f"ps aux --sort=-%cpu | head -{limit + 1}")
            
            lines = ps_output.strip().split('\n')
            processes = []
            
            if len(lines) > 1:
                # Skip header line
                for line in lines[1:]:
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        process = {
                            'user': parts[0],
                            'pid': parts[1],
                            'cpu_percent': parts[2],
                            'memory_percent': parts[3],
                            'vsz': parts[4],
                            'rss': parts[5],
                            'tty': parts[6],
                            'stat': parts[7],
                            'start': parts[8],
                            'time': parts[9],
                            'command': parts[10]
                        }
                        processes.append(process)
            
            return processes
            
        except Exception as e:
            self.logger.error(f"Failed to get process list: {e}")
            return []
    
    async def test_connection(self) -> bool:
        """
        Test SSH connection.
        
        Returns:
            bool: True if connection is working
        """
        try:
            result = await self.execute_command('echo "test"', timeout=5)
            return result.strip() == "test"
        except Exception:
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information."""
        if not self.config:
            return {'connected': False}
        
        return {
            'connected': self.is_connected,
            'host': self.config.host,
            'port': self.config.port,
            'username': self.config.username,
            'auth_method': 'key' if self.config.private_key or self.config.private_key_path else 'password',
            'timeout': self.config.timeout,
            'host_key_checking': self.config.host_key_checking
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()