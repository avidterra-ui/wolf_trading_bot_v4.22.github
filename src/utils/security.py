"""
Security utilities for Wolf Trading Bot.
Handles secure configuration loading and API key management.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv


class SecureConfigLoader:
    """
    Secure configuration loader that handles environment variable substitution
    and ensures sensitive data is properly managed.
    """
    
    # Pattern to match ${ENV_VAR} or $ENV_VAR
    ENV_PATTERN = re.compile(r'\$\{?([A-Z_][A-Z0-9_]*)\}?')
    
    # Sensitive keys that should ONLY come from environment variables
    SENSITIVE_KEYS = [
        'api_id', 'api_hash', 'api_key', 'api_secret',
        'password', 'token', 'secret'
    ]
    
    def __init__(self, env_file: str = ".env"):
        """Initialize with optional .env file path."""
        self.env_file = env_file
        self._load_env()
    
    def _load_env(self) -> None:
        """Load environment variables from .env file if exists."""
        env_path = Path(self.env_file)
        if env_path.exists():
            load_dotenv(env_path)
    
    def _substitute_env_vars(self, value: Any) -> Any:
        """Recursively substitute environment variables in config values."""
        if isinstance(value, str):
            # Find all environment variable references
            matches = self.ENV_PATTERN.findall(value)
            for match in matches:
                env_value = os.getenv(match)
                if env_value is not None:
                    value = value.replace(f'${{{match}}}', env_value)
                    value = value.replace(f'${match}', env_value)
            return value
        elif isinstance(value, dict):
            return {k: self._substitute_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._substitute_env_vars(item) for item in value]
        return value
    
    def _check_sensitive_keys(self, config: dict, path: str = "") -> list:
        """Check if sensitive keys have values directly in config (security risk)."""
        warnings = []
        for key, value in config.items():
            current_path = f"{path}.{key}" if path else key
            
            if isinstance(value, dict):
                warnings.extend(self._check_sensitive_keys(value, current_path))
            elif isinstance(value, str):
                # Check if this is a sensitive key with a hardcoded value
                is_sensitive = any(s in key.lower() for s in self.SENSITIVE_KEYS)
                is_env_ref = self.ENV_PATTERN.search(value) is not None
                is_placeholder = value.startswith('your_') or value == ''
                
                if is_sensitive and not is_env_ref and not is_placeholder:
                    warnings.append(
                        f"WARNING: Sensitive key '{current_path}' appears to have "
                        f"a hardcoded value. Use environment variables instead."
                    )
        return warnings
    
    def load_config(self, config_path: str = "config/config.yaml") -> dict:
        """
        Load and validate configuration file.
        
        Args:
            config_path: Path to YAML configuration file
            
        Returns:
            Parsed and validated configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If required environment variables are missing
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Check for security issues
        warnings = self._check_sensitive_keys(config)
        for warning in warnings:
            print(f"\033[33m{warning}\033[0m")  # Yellow warning
        
        # Substitute environment variables
        config = self._substitute_env_vars(config)
        
        # Validate required values are present
        self._validate_config(config)
        
        return config
    
    def _validate_config(self, config: dict) -> None:
        """Validate that required configuration values are present."""
        required_paths = [
            ('telegram', 'api_id'),
            ('telegram', 'api_hash'),
        ]
        
        for path in required_paths:
            value = config
            for key in path:
                if key not in value:
                    raise ValueError(
                        f"Missing required configuration: {'.'.join(path)}. "
                        f"Set the corresponding environment variable."
                    )
                value = value[key]
            
            if not value or str(value).startswith('${'):
                raise ValueError(
                    f"Configuration '{'.'.join(path)}' is not set. "
                    f"Please set the environment variable."
                )
    
    @staticmethod
    def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
        """Safely get an environment variable."""
        return os.getenv(key, default)
    
    @staticmethod
    def require_env(key: str) -> str:
        """Get a required environment variable or raise error."""
        value = os.getenv(key)
        if not value:
            raise ValueError(
                f"Required environment variable '{key}' is not set. "
                f"Please set it in your .env file or environment."
            )
        return value


def redact_sensitive(data: dict, keys_to_redact: list = None) -> dict:
    """
    Redact sensitive values from a dictionary for logging.
    
    Args:
        data: Dictionary to redact
        keys_to_redact: List of key patterns to redact
        
    Returns:
        Dictionary with sensitive values replaced with [REDACTED]
    """
    if keys_to_redact is None:
        keys_to_redact = ['key', 'secret', 'password', 'token', 'hash', 'api_id']
    
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = redact_sensitive(value, keys_to_redact)
        elif any(pattern in key.lower() for pattern in keys_to_redact):
            result[key] = '[REDACTED]'
        else:
            result[key] = value
    
    return result
