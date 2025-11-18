"""
Logging configuration utility for Obsidian RAG system

Provides consistent logging setup across all modules.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
    module_name: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging configuration for a module.
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file
        format_string: Optional custom format string
        module_name: Name of the module (for logger name)
    
    Returns:
        Configured logger instance
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Create formatter
    formatter = logging.Formatter(format_string)
    
    # Get or create logger
    if module_name:
        logger = logging.getLogger(module_name)
    else:
        # Get caller's module name
        import inspect
        frame = inspect.currentframe().f_back
        module_name = frame.f_globals.get('__name__', 'root')
        logger = logging.getLogger(module_name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Set level
    logger.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    This is a convenience function that returns a logger without
    configuring handlers (assumes logging is already configured).
    
    Args:
        name: Logger name (defaults to calling module's __name__)
    
    Returns:
        Logger instance
    """
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'root')
    
    return logging.getLogger(name)

