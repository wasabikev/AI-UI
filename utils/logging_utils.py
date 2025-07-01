# utils/logging_utils.py

import logging
import sys
from logging.handlers import RotatingFileHandler

class UnicodeFormatter(logging.Formatter):
    """Custom formatter that properly handles Unicode characters in log messages."""
    def format(self, record):
        try:
            # Handle bytes and non-string messages
            if isinstance(record.msg, bytes):
                record.msg = record.msg.decode('utf-8', errors='replace')
            elif not isinstance(record.msg, str):
                record.msg = str(record.msg)

            # Handle bytes in args
            if record.args:
                safe_args = []
                for arg in record.args:
                    if isinstance(arg, bytes):
                        safe_args.append(arg.decode('utf-8', errors='replace'))
                    else:
                        arg_str = str(arg)
                        if len(arg_str) > 1000:
                            arg_str = arg_str[:500] + "...[truncated]..." + arg_str[-100:]
                        safe_args.append(arg_str)
                record.args = tuple(safe_args)

            try:
                return super().format(record)
            except TypeError:
                # Fallback for argument mismatch (e.g., 3rd-party SDKs)
                record.msg = str(record.msg)
                record.args = ()
                return super().format(record)
        except Exception:
            record.msg = f"LOGGING ERROR: Could not format message safely"
            record.args = ()
            return super().format(record)


class ColorFormatter(logging.Formatter):
    """Add colors to log levels with safe message handling"""
    grey = "\x1b[38;21m"
    blue = "\x1b[34;21m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    FORMATS = {
        logging.DEBUG: blue + "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s" + reset,
        logging.INFO: grey + "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s" + reset,
        logging.WARNING: yellow + "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s" + reset,
        logging.ERROR: red + "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s" + reset,
        logging.CRITICAL: bold_red + "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s" + reset,
    }
    
    def format(self, record):
        try:
            if hasattr(record, 'msg') and isinstance(record.msg, str) and len(record.msg) > 2000:
                record.msg = record.msg[:1000] + "...[truncated]..." + record.msg[-500:]
            log_fmt = self.FORMATS.get(record.levelno, self.FORMATS[logging.INFO])
            formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
            try:
                return formatter.format(record)
            except TypeError:
                # Fallback for argument mismatch (e.g., 3rd-party SDKs)
                record.msg = str(record.msg)
                record.args = ()
                return formatter.format(record)
        except Exception:
            return f"{self.grey}{self.formatTime(record)} - ERROR - LOGGING FORMAT ERROR{self.reset}"

def setup_logging(app, debug_mode):
    """Setup logging configuration with improved duplication prevention."""
    
    # Clear ALL existing handlers from ALL loggers to start completely fresh
    logging.getLogger().handlers.clear()
    app.logger.handlers.clear()
    
    # Clear handlers from any existing loggers that might cause issues
    for name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(name)
        logger.handlers.clear()
    
    # Configure root logger with basicConfig (essential for third-party libraries)
    logging.basicConfig(
        level=logging.DEBUG if debug_mode else logging.INFO,
        format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True  # Force reconfiguration
    )
    
    # Custom Unicode formatter
    unicode_formatter = UnicodeFormatter("%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s")

    # Set up file handler with rotation
    try:
        file_handler = RotatingFileHandler(
            "app.log",
            maxBytes=100000,
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setFormatter(unicode_formatter)
        file_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    except Exception as e:
        print(f"Warning: Could not create file handler: {e}")
        file_handler = None

    # Console handler with color formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter())
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # Get the root logger and configure it properly
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Clear again to be absolutely sure
    root_logger.addHandler(console_handler)
    if file_handler:
        root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # Configure app logger to propagate only (no direct handlers)
    app.logger.handlers.clear()
    app.logger.propagate = True
    app.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # Completely silence SQLAlchemy logging
    sqlalchemy_loggers = [
        'sqlalchemy',
        'sqlalchemy.engine',
        'sqlalchemy.engine.base.Engine',
        'sqlalchemy.dialects',
        'sqlalchemy.pool',
        'sqlalchemy.orm',
        'sqlalchemy.engine.base',
        'sqlalchemy.engine.impl',
        'sqlalchemy.engine.logger'
    ]
    
    for logger_name in sqlalchemy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)
        logger.handlers.clear()
        logger.propagate = True

    # Disable SQL statement logging explicitly
    logging.getLogger('sqlalchemy.engine.Engine.logger').disabled = True

    # Configure third-party loggers with appropriate levels
    noisy_loggers = [
        'httpcore',
        'hypercorn.error', 
        'hypercorn.access',
        'pinecone',
        'asyncio',
        'httpx',
        'urllib3',
        'requests',
        'pinecone_plugin_interface.logging'
    ]

    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
        logger.propagate = True

    # Handle unstract loggers that were causing duplication
    unstract_loggers = [
        'unstract',
        'unstract.llmwhisperer.client',
        'unstract.llmwhisperer.client_v2'
    ]
    
    for logger_name in unstract_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING if not debug_mode else logging.INFO)
        logger.handlers.clear()
        logger.propagate = True

    # Handle OpenAI client logger specifically to prevent the massive duplication
    openai_logger = logging.getLogger('openai')
    openai_logger.setLevel(logging.INFO if debug_mode else logging.WARNING)
    openai_logger.handlers.clear()
    openai_logger.propagate = True
    
    # Also handle the specific _base_client logger
    openai_base_logger = logging.getLogger('openai._base_client')
    openai_base_logger.setLevel(logging.INFO if debug_mode else logging.WARNING)
    openai_base_logger.handlers.clear()
    openai_base_logger.propagate = True

    # Log startup message
    app.logger.info("Application logging initialized")
    if debug_mode:
        app.logger.debug("Debug mode enabled")
        app.logger.debug("Console logging enabled with colors")
