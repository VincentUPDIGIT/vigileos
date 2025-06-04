"""
Cross-platform logging utilities.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

from utils.platform_utils import PlatformPaths


class ColoredFormatter(logging.Formatter):
    """Colored log formatter for console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        """Format log record with colors."""
        if hasattr(record, 'levelname'):
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


def setup_logger(name: str = "network_agent", 
                level: str = "INFO",
                log_file: Optional[Path] = None,
                console_output: bool = True,
                colored_output: bool = True,
                structured_logging: bool = False,
                max_file_size: int = 10 * 1024 * 1024,  # 10MB
                backup_count: int = 5) -> logging.Logger:
    """
    Setup cross-platform logger with file and console handlers.
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Log file path (auto-generated if None)
        console_output: Whether to output to console
        colored_output: Whether to use colored console output
        structured_logging: Whether to use structured logging (requires structlog)
        max_file_size: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        
    Returns:
        logging.Logger: Configured logger
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatters
    if structured_logging and STRUCTLOG_AVAILABLE:
        # Use structured logging
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        formatter = logging.Formatter('%(message)s')
    else:
        # Standard logging format
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        
        if colored_output and not structured_logging:
            console_formatter = ColoredFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
        else:
            console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    # File handler
    if log_file is None:
        log_dir = PlatformPaths.get_log_dir()
        PlatformPaths.ensure_directory_exists(log_dir)
        log_file = log_dir / f"{name}.log"
    
    try:
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    except Exception as e:
        # If file logging fails, log to console
        logger.warning(f"Failed to setup file logging: {e}")
    
    # Add system info to first log
    logger.info(f"Logger '{name}' initialized at level {level}")
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get existing logger or create a basic one.
    
    Args:
        name: Logger name (uses calling module if None)
        
    Returns:
        logging.Logger: Logger instance
    """
    if name is None:
        # Get caller's module name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    logger = logging.getLogger(name)
    
    # If logger has no handlers, set up basic logging
    if not logger.handlers:
        logger = setup_logger(name)
    
    return logger


class LogContext:
    """Context manager for adding context to logs."""
    
    def __init__(self, logger: logging.Logger, **context):
        """
        Initialize log context.
        
        Args:
            logger: Logger to add context to
            **context: Context key-value pairs
        """
        self.logger = logger
        self.context = context
        self.old_factory = None
    
    def __enter__(self):
        """Enter context manager."""
        if STRUCTLOG_AVAILABLE:
            # Use structlog context
            self.bound_logger = structlog.get_logger(self.logger.name).bind(**self.context)
            return self.bound_logger
        else:
            # Add context to standard logger
            self.old_factory = logging.getLogRecordFactory()
            
            def record_factory(*args, **kwargs):
                record = self.old_factory(*args, **kwargs)
                for key, value in self.context.items():
                    setattr(record, key, value)
                return record
            
            logging.setLogRecordFactory(record_factory)
            return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if not STRUCTLOG_AVAILABLE and self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


class PerformanceLogger:
    """Logger for performance monitoring."""
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize performance logger.
        
        Args:
            logger: Base logger to use
        """
        self.logger = logger
        self.start_time = None
    
    def start(self, operation: str):
        """Start timing an operation."""
        self.operation = operation
        self.start_time = datetime.utcnow()
        self.logger.debug(f"Started operation: {operation}")
    
    def end(self, success: bool = True, **context):
        """End timing an operation."""
        if self.start_time is None:
            self.logger.warning("Performance timing ended without start")
            return
        
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()
        
        log_data = {
            'operation': self.operation,
            'duration_seconds': duration,
            'success': success,
            **context
        }
        
        if success:
            self.logger.info(f"Completed operation: {self.operation} in {duration:.3f}s", extra=log_data)
        else:
            self.logger.error(f"Failed operation: {self.operation} after {duration:.3f}s", extra=log_data)
        
        self.start_time = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        success = exc_type is None
        error_info = {}
        
        if not success:
            error_info = {
                'error_type': exc_type.__name__ if exc_type else None,
                'error_message': str(exc_val) if exc_val else None
            }
        
        self.end(success=success, **error_info)


def log_function_call(logger: logging.Logger = None, level: str = "DEBUG"):
    """
    Decorator to log function calls.
    
    Args:
        logger: Logger to use (creates one if None)
        level: Log level for function calls
        
    Returns:
        Decorator function
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
        
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__name__}"
            
            # Log function entry
            getattr(logger, level.lower())(f"Entering function: {func_name}")
            
            try:
                result = func(*args, **kwargs)
                getattr(logger, level.lower())(f"Exiting function: {func_name}")
                return result
            except Exception as e:
                logger.error(f"Function {func_name} raised exception: {e}")
                raise
        
        return wrapper
    return decorator


def log_async_function_call(logger: logging.Logger = None, level: str = "DEBUG"):
    """
    Decorator to log async function calls.
    
    Args:
        logger: Logger to use (creates one if None)
        level: Log level for function calls
        
    Returns:
        Decorator function
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
        
        async def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__name__}"
            
            # Log function entry
            getattr(logger, level.lower())(f"Entering async function: {func_name}")
            
            try:
                result = await func(*args, **kwargs)
                getattr(logger, level.lower())(f"Exiting async function: {func_name}")
                return result
            except Exception as e:
                logger.error(f"Async function {func_name} raised exception: {e}")
                raise
        
        return wrapper
    return decorator


class LoggingConfig:
    """Centralized logging configuration."""
    
    DEFAULT_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'standard',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'filename': 'network_agent.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf-8'
            }
        },
        'loggers': {
            'network_agent': {
                'level': 'DEBUG',
                'handlers': ['console', 'file'],
                'propagate': False
            },
            'aiohttp': {
                'level': 'WARNING',
                'handlers': ['console', 'file'],
                'propagate': False
            },
            'asyncio': {
                'level': 'WARNING',
                'handlers': ['console', 'file'],
                'propagate': False
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['console']
        }
    }
    
    @classmethod
    def setup_from_dict(cls, config: Dict[str, Any] = None):
        """
        Setup logging from dictionary configuration.
        
        Args:
            config: Logging configuration dictionary
        """
        import logging.config
        
        if config is None:
            config = cls.DEFAULT_CONFIG.copy()
            
            # Update file path to use platform-specific location
            log_dir = PlatformPaths.get_log_dir()
            PlatformPaths.ensure_directory_exists(log_dir)
            config['handlers']['file']['filename'] = str(log_dir / 'network_agent.log')
        
        logging.config.dictConfig(config)
    
    @classmethod
    def setup_from_file(cls, config_file: Path):
        """
        Setup logging from configuration file.
        
        Args:
            config_file: Path to configuration file (JSON or YAML)
        """
        import json
        
        try:
            with open(config_file, 'r') as f:
                if config_file.suffix.lower() in ['.yaml', '.yml']:
                    try:
                        import yaml
                        config = yaml.safe_load(f)
                    except ImportError:
                        raise ImportError("PyYAML required for YAML config files")
                else:
                    config = json.load(f)
            
            cls.setup_from_dict(config)
            
        except Exception as e:
            # Fallback to default configuration
            print(f"Failed to load logging config from {config_file}: {e}")
            cls.setup_from_dict()


# Convenience functions for common logging patterns

def log_system_info(logger: logging.Logger):
    """Log system information."""
    from utils.platform_utils import PlatformUtils
    
    info = PlatformUtils.get_platform_info()
    logger.info("System Information:")
    for key, value in info.items():
        logger.info(f"  {key}: {value}")


def log_performance_stats(logger: logging.Logger, stats: Dict[str, Any]):
    """Log performance statistics."""
    logger.info("Performance Statistics:")
    for key, value in stats.items():
        if isinstance(value, float):
            logger.info(f"  {key}: {value:.3f}")
        else:
            logger.info(f"  {key}: {value}")


def setup_application_logging(app_name: str = "network_agent",
                            log_level: str = "INFO",
                            enable_file_logging: bool = True,
                            enable_console_logging: bool = True) -> logging.Logger:
    """
    Setup application-wide logging configuration.
    
    Args:
        app_name: Application name for logger
        log_level: Default log level
        enable_file_logging: Whether to enable file logging
        enable_console_logging: Whether to enable console logging
        
    Returns:
        logging.Logger: Main application logger
    """
    # Setup main logger
    logger = setup_logger(
        name=app_name,
        level=log_level,
        console_output=enable_console_logging
    )
    
    # Log system information
    log_system_info(logger)
    
    return logger