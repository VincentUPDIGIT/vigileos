"""
Platform factory for automatic platform detection and instantiation.
"""

import platform
import sys
from typing import Type

from platforms.base_platform import BasePlatform, PlatformError


class UnsupportedPlatformError(PlatformError):
    """Exception raised when the platform is not supported."""
    pass


class PlatformFactory:
    """
    Factory class for creating platform-specific instances.
    
    Automatically detects the current platform and returns the appropriate
    platform implementation.
    """
    
    _platform_cache = None
    
    @staticmethod
    def get_platform() -> BasePlatform:
        """
        Get the appropriate platform instance for the current system.
        
        Returns:
            BasePlatform: Platform-specific implementation instance
            
        Raises:
            UnsupportedPlatformError: If the current platform is not supported
        """
        # Use cached instance if available
        if PlatformFactory._platform_cache is not None:
            return PlatformFactory._platform_cache
        
        system = platform.system().lower()
        
        try:
            if system == 'linux':
                from platforms.linux_platform import LinuxPlatform
                PlatformFactory._platform_cache = LinuxPlatform()
            elif system == 'windows':
                from platforms.windows_platform import WindowsPlatform
                PlatformFactory._platform_cache = WindowsPlatform()
            elif system == 'darwin':  # macOS
                from platforms.macos_platform import MacOSPlatform
                PlatformFactory._platform_cache = MacOSPlatform()
            else:
                raise UnsupportedPlatformError(
                    f"Platform '{system}' is not supported. "
                    f"Supported platforms: Linux, Windows, macOS",
                    platform=system
                )
        except ImportError as e:
            raise UnsupportedPlatformError(
                f"Failed to import platform implementation for '{system}': {e}",
                platform=system
            )
        
        return PlatformFactory._platform_cache
    
    @staticmethod
    def get_platform_type() -> Type[BasePlatform]:
        """
        Get the platform class type without instantiating.
        
        Returns:
            Type[BasePlatform]: Platform class type
            
        Raises:
            UnsupportedPlatformError: If the current platform is not supported
        """
        system = platform.system().lower()
        
        if system == 'linux':
            from platforms.linux_platform import LinuxPlatform
            return LinuxPlatform
        elif system == 'windows':
            from platforms.windows_platform import WindowsPlatform
            return WindowsPlatform
        elif system == 'darwin':  # macOS
            from platforms.macos_platform import MacOSPlatform
            return MacOSPlatform
        else:
            raise UnsupportedPlatformError(
                f"Platform '{system}' is not supported",
                platform=system
            )
    
    @staticmethod
    def get_platform_name() -> str:
        """
        Get the current platform name.
        
        Returns:
            str: Platform name (linux, windows, macos)
        """
        system = platform.system().lower()
        if system == 'darwin':
            return 'macos'
        return system
    
    @staticmethod
    def is_supported_platform() -> bool:
        """
        Check if the current platform is supported.
        
        Returns:
            bool: True if platform is supported
        """
        try:
            PlatformFactory.get_platform_type()
            return True
        except UnsupportedPlatformError:
            return False
    
    @staticmethod
    def get_platform_info() -> dict:
        """
        Get detailed platform information.
        
        Returns:
            dict: Platform information including system, version, architecture
        """
        return {
            'system': platform.system(),
            'platform': PlatformFactory.get_platform_name(),
            'version': platform.version(),
            'release': platform.release(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'architecture': platform.architecture(),
            'python_version': sys.version,
            'python_implementation': platform.python_implementation(),
            'is_supported': PlatformFactory.is_supported_platform()
        }
    
    @staticmethod
    def clear_cache():
        """Clear the cached platform instance."""
        PlatformFactory._platform_cache = None