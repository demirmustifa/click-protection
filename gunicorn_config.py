import multiprocessing

# Server ayarları
bind = "0.0.0.0:10000"
workers = 1  # Tek worker kullan
worker_class = "sync"  # Senkron worker kullan
timeout = 300  # Timeout süresini artır

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Worker ayarları
preload_app = True
max_requests = 0  # Worker yeniden başlatma limitini kaldır 