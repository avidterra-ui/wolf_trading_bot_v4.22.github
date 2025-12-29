"""
Logging configuration for Wolf Trading Bot.
Supports JSON file logging and colored console output.
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import sys


class JSONFormatter(logging.Formatter):
    """JSON formatter for file logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields but exclude sensitive data
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 
                          'funcName', 'levelname', 'levelno', 'lineno',
                          'module', 'msecs', 'pathname', 'process',
                          'processName', 'relativeCreated', 'stack_info',
                          'exc_info', 'exc_text', 'thread', 'threadName',
                          'message']:
                # Filter sensitive data
                if any(sensitive in str(key).lower() for sensitive in 
                      ['key', 'secret', 'password', 'token', 'hash']):
                    log_data[key] = '[REDACTED]'
                else:
                    log_data[key] = value
        
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now().strftime('%H:%M:%S')
        return f"{color}[{timestamp}] {record.levelname}: {record.getMessage()}{self.RESET}"


def setup_logging(
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    console_output: bool = True
) -> None:
    """
    Setup logging configuration.
    
    Args:
        log_dir: Directory for log files
        log_level: Logging level
        console_output: Whether to output to console
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # File handler (JSON format, daily rotation)
    today = datetime.now().strftime('%Y-%m-%d')
    file_handler = logging.FileHandler(
        log_path / f"wolf_bot_{today}.json",
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)
    
    # Console handler (colored, minimal output to not interfere with rich)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)  # Only warnings and above
        console_handler.setFormatter(ColoredFormatter())
        root_logger.addHandler(console_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger('telethon').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)
