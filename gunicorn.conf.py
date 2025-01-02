import multiprocessing
import os

# Gunicorn config
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
keepalive = 65

# Worker configurations
worker_connections = 1000
timeout = 300
graceful_timeout = 30

# Logging
loglevel = "debug"

# WebSocket specific settings
websocket_ping_interval = 20
websocket_ping_timeout = 30
websocket_max_message_size = 1048576  # 1MB

# Forward-facing proxy settings
forwarded_allow_ips = '*'
proxy_allow_ips = '*'
proxy_protocol = True

# Process naming
proc_name = "ai-ui"

# Worker class settings
worker_class = "uvicorn.workers.UvicornWorker"