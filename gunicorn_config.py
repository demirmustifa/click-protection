import multiprocessing

# Server ayarları
bind = "0.0.0.0:10000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
worker_connections = 1000

# Timeout ayarları
timeout = 60
keepalive = 30
graceful_timeout = 60

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Worker ayarları
preload_app = True
max_requests = 1000
max_requests_jitter = 50

# Security settings
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190 