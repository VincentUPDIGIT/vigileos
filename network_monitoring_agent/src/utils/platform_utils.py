"""
Cross-platform utility functions and path management.
"""

import os
import platform
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Union

from platforms.platform_factory import PlatformFactory


class PlatformPaths:
    """Cross-platform path management utility."""
    
    @staticmethod
    def get_config_dir() -> Path:
        """Get the configuration directory for the current platform."""
        try:
            platform_instance = PlatformFactory.get_platform()
            return platform_instance.get_default_config_path()
        except Exception:
            # Fallback to platform-specific defaults
            system = platform.system()
            if system == 'Windows':
                return Path.home() / 'AppData/Roaming/NetworkAgent'
            elif system == 'Darwin':  # macOS
                return Path.home() / 'Library/Application Support/NetworkAgent'
            else:  # Linux and others
                return Path.home() / '.config/network-agent'
    
    @staticmethod
    def get_log_dir() -> Path:
        """Get the log directory for the current platform."""
        try:
            platform_instance = PlatformFactory.get_platform()
            return platform_instance.get_default_log_path()
        except Exception:
            # Fallback to platform-specific defaults
            system = platform.system()
            if system == 'Windows':
                return Path.home() / 'AppData/Local/NetworkAgent/logs'
            elif system == 'Darwin':  # macOS
                return Path.home() / 'Library/Logs/NetworkAgent'
            else:  # Linux and others
                return Path('/var/log/network-agent')
    
    @staticmethod
    def get_data_dir() -> Path:
        """Get the data directory for the current platform."""
        system = platform.system()
        if system == 'Windows':
            return Path.home() / 'AppData/Local/NetworkAgent/data'
        elif system == 'Darwin':  # macOS
            return Path.home() / 'Library/Application Support/NetworkAgent/data'
        else:  # Linux and others
            return Path.home() / '.local/share/network-agent'
    
    @staticmethod
    def get_cache_dir() -> Path:
        """Get the cache directory for the current platform."""
        system = platform.system()
        if system == 'Windows':
            return Path.home() / 'AppData/Local/NetworkAgent/cache'
        elif system == 'Darwin':  # macOS
            return Path.home() / 'Library/Caches/NetworkAgent'
        else:  # Linux and others
            return Path.home() / '.cache/network-agent'
    
    @staticmethod
    def get_temp_dir() -> Path:
        """Get the temporary directory for the current platform."""
        try:
            platform_instance = PlatformFactory.get_platform()
            return platform_instance.get_temp_path()
        except Exception:
            # Fallback to standard temp directory
            return Path(os.environ.get('TEMP', os.environ.get('TMP', '/tmp')))
    
    @staticmethod
    def get_service_config_path() -> Path:
        """Get the service configuration file path for the current platform."""
        try:
            platform_instance = PlatformFactory.get_platform()
            return platform_instance.get_service_config_path()
        except Exception:
            # Fallback to platform-specific defaults
            system = platform.system()
            if system == 'Windows':
                return Path('C:/ProgramData/NetworkAgent/service.yaml')
            elif system == 'Darwin':  # macOS
                return Path('/Library/LaunchDaemons/com.company.networkagent.plist')
            else:  # Linux and others
                return Path('/etc/systemd/system/network-agent.service')
    
    @staticmethod
    def get_executable_extension() -> str:
        """Get the executable file extension for the current platform."""
        return '.exe' if platform.system() == 'Windows' else ''
    
    @staticmethod
    def get_config_file_extension() -> str:
        """Get the preferred configuration file extension for the current platform."""
        return '.yaml'  # YAML is cross-platform
    
    @staticmethod
    def normalize_path(path: Union[str, Path]) -> Path:
        """Normalize a path for the current platform."""
        path = Path(path)
        
        # Expand user directory
        if str(path).startswith('~'):
            path = path.expanduser()
        
        # Resolve relative paths
        if not path.is_absolute():
            path = path.resolve()
        
        return path
    
    @staticmethod
    def ensure_directory_exists(directory: Union[str, Path], mode: int = 0o755) -> bool:
        """Ensure a directory exists, creating it if necessary."""
        try:
            directory = PlatformPaths.normalize_path(directory)
            directory.mkdir(parents=True, exist_ok=True, mode=mode)
            return True
        except Exception:
            return False
    
    @staticmethod
    def is_path_writable(path: Union[str, Path]) -> bool:
        """Check if a path is writable."""
        try:
            path = PlatformPaths.normalize_path(path)
            
            if path.is_file():
                return os.access(path, os.W_OK)
            elif path.is_dir():
                # Try to create a temporary file
                test_file = path / '.write_test'
                try:
                    test_file.touch()
                    test_file.unlink()
                    return True
                except:
                    return False
            else:
                # Check parent directory
                return PlatformPaths.is_path_writable(path.parent)
        except Exception:
            return False


class PlatformUtils:
    """General cross-platform utility functions."""
    
    @staticmethod
    def get_platform_info() -> Dict[str, Any]:
        """Get comprehensive platform information."""
        try:
            platform_instance = PlatformFactory.get_platform()
            platform_info = platform_instance.get_platform_info()
        except Exception:
            platform_info = {}
        
        # Add additional platform information
        platform_info.update({
            'system': platform.system(),
            'platform': platform.platform(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'architecture': platform.architecture(),
            'python_version': sys.version,
            'python_implementation': platform.python_implementation(),
            'python_executable': sys.executable,
            'is_64bit': sys.maxsize > 2**32,
            'byte_order': sys.byteorder,
            'encoding': sys.getdefaultencoding(),
            'file_system_encoding': sys.getfilesystemencoding(),
        })
        
        return platform_info
    
    @staticmethod
    def is_admin() -> bool:
        """Check if the current process has administrative privileges."""
        try:
            platform_instance = PlatformFactory.get_platform()
            return platform_instance.is_admin()
        except Exception:
            return False
    
    @staticmethod
    def get_current_user() -> str:
        """Get the current username."""
        return os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
    
    @staticmethod
    def get_hostname() -> str:
        """Get the system hostname."""
        return platform.node()
    
    @staticmethod
    def get_environment_variables() -> Dict[str, str]:
        """Get relevant environment variables."""
        relevant_vars = [
            'PATH', 'HOME', 'USER', 'USERNAME', 'USERPROFILE',
            'TEMP', 'TMP', 'TMPDIR', 'APPDATA', 'LOCALAPPDATA',
            'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME'
        ]
        
        env_vars = {}
        for var in relevant_vars:
            value = os.environ.get(var)
            if value:
                env_vars[var] = value
        
        return env_vars
    
    @staticmethod
    def get_system_encoding() -> str:
        """Get the system's preferred encoding."""
        return sys.getdefaultencoding()
    
    @staticmethod
    def is_virtual_environment() -> bool:
        """Check if running in a virtual environment."""
        return (
            hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        )
    
    @staticmethod
    def get_python_info() -> Dict[str, Any]:
        """Get Python interpreter information."""
        return {
            'version': sys.version,
            'version_info': sys.version_info,
            'implementation': platform.python_implementation(),
            'executable': sys.executable,
            'prefix': sys.prefix,
            'base_prefix': getattr(sys, 'base_prefix', sys.prefix),
            'real_prefix': getattr(sys, 'real_prefix', None),
            'is_virtual_env': PlatformUtils.is_virtual_environment(),
            'path': sys.path[:5],  # First 5 entries
        }
    
    @staticmethod
    def format_bytes(bytes_value: int) -> str:
        """Format bytes in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        elif seconds < 86400:
            hours = seconds / 3600
            return f"{hours:.1f}h"
        else:
            days = seconds / 86400
            return f"{days:.1f}d"
    
    @staticmethod
    def safe_filename(filename: str) -> str:
        """Create a safe filename by removing/replacing invalid characters."""
        # Characters that are invalid in filenames on various platforms
        invalid_chars = '<>:"/\\|?*'
        
        # Replace invalid characters with underscores
        safe_name = ''.join('_' if c in invalid_chars else c for c in filename)
        
        # Remove leading/trailing dots and spaces
        safe_name = safe_name.strip('. ')
        
        # Ensure the filename is not empty
        if not safe_name:
            safe_name = 'unnamed'
        
        # Truncate if too long (255 is a common filesystem limit)
        if len(safe_name) > 255:
            safe_name = safe_name[:255]
        
        return safe_name
    
    @staticmethod
    def get_free_port(start_port: int = 8000, max_attempts: int = 100) -> Optional[int]:
        """Find a free port starting from the given port."""
        import socket
        
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind(('localhost', port))
                    return port
            except OSError:
                continue
        
        return None
    
    @staticmethod
    def is_port_open(host: str, port: int, timeout: float = 3.0) -> bool:
        """Check if a port is open on a host."""
        import socket
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((host, port))
                return result == 0
        except Exception:
            return False
    
    @staticmethod
    def get_local_ip() -> str:
        """Get the local IP address."""
        import socket
        
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except Exception:
            return "127.0.0.1"
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate an IP address."""
        import ipaddress
        
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_port(port: Union[str, int]) -> bool:
        """Validate a port number."""
        try:
            port_num = int(port)
            return 1 <= port_num <= 65535
        except (ValueError, TypeError):
            return False