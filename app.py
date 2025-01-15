from flask import Flask, jsonify, request, render_template, send_file, redirect
from datetime import datetime, timedelta
import logging
import json
from collections import deque, Counter, defaultdict
import threading
import time
import requests
import os
from flask_mail import Mail, Message
import pandas as pd
import io
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import geoip2.database
from geoip2.errors import AddressNotFoundError
from flask_cors import CORS
import redis
import hashlib

# Loglama ayarlarını yapılandır
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["https://servisimonline.com", "http://servisimonline.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-Forwarded-For"]
    }
})

# Redis bağlantısı
redis_url = os.getenv('REDIS_URL')
redis_client = None

if redis_url:
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        logger.info("Redis bağlantısı başarılı")
    except Exception as e:
        logger.error(f"Redis bağlantı hatası: {str(e)}")
        redis_client = None
else:
    logger.warning("REDIS_URL bulunamadı, memory storage kullanılacak")

# E-posta yapılandırması
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)

class ClickFraudDetector:
    def __init__(self):
        self.clicks = deque(maxlen=500)
        self.suspicious_activities = deque(maxlen=50)
        self.admin_email = os.getenv('ADMIN_EMAIL')
        self.location_data = []
        self.country_stats = Counter()
        self.memory_storage = {}  # Redis çalışmazsa memory'de tut
        
    def get_click_count(self, ip, campaign_id=None):
        """IP için tıklama sayısını al"""
        try:
            if redis_client:
                key = f"clicks:{ip}"
                if campaign_id:
                    key += f":{campaign_id}"
                clicks = redis_client.get(key)
                return int(clicks) if clicks else 0
            else:
                key = f"{ip}:{campaign_id}" if campaign_id else ip
                return self.memory_storage.get(key, 0)
        except:
            return self.memory_storage.get(ip, 0)

    def increment_click_count(self, ip, campaign_id=None):
        """IP için tıklama sayısını artır"""
        try:
            if redis_client:
                key = f"clicks:{ip}"
                if campaign_id:
                    key += f":{campaign_id}"
                redis_client.incr(key)
                redis_client.expire(key, 3600)
            else:
                key = f"{ip}:{campaign_id}" if campaign_id else ip
                self.memory_storage[key] = self.memory_storage.get(key, 0) + 1
        except:
            key = f"{ip}:{campaign_id}" if campaign_id else ip
            self.memory_storage[key] = self.memory_storage.get(key, 0) + 1

    def check_click(self, ip, campaign_id, user_agent):
        """Tıklama kontrolü"""
        try:
            # Tıklama sayısı kontrolü
            click_count = self.get_click_count(ip, campaign_id)
            logger.info(f"IP: {ip}, Tıklama sayısı: {click_count}")
            
            if click_count >= 2:  # 2'den fazla tıklamada engelle
                logger.warning(f"IP limit aşımı: {ip}")
                return False, "IP limiti aşıldı"

            # Tıklama sayısını artır
            self.increment_click_count(ip, campaign_id)
            
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Tıklama kontrolü hatası: {str(e)}")
            return True, "Hata durumunda izin ver"

@app.route('/')
def index():
    """Ana sayfa yönlendirmesi"""
    try:
        gclid = request.args.get('gclid')
        campaign_id = request.args.get('utm_campaign', 'default')
        ip = request.remote_addr or request.headers.get('X-Forwarded-For', '').split(',')[0]
        user_agent = request.headers.get('User-Agent', '')

        # Tıklama kontrolü
        is_valid, reason = detector.check_click(ip, campaign_id, user_agent)
        logger.info(f"Kontrol sonucu: {is_valid}, {reason}")

        if not is_valid:
            return render_template('bot-saldirisi.html')

        target_url = f'https://servisimonline.com/?gclid={gclid}&utm_source=google&utm_medium=cpc&utm_campaign={campaign_id}'
        return redirect(target_url)

    except Exception as e:
        logger.error(f"Ana sayfa hatası: {str(e)}")
        return render_template('bot-saldirisi.html')

@app.route('/bot-saldirisi.html')
def bot_page():
    """Bot sayfası"""
    return render_template('bot-saldirisi.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard sayfası"""
    try:
        # Memory storage veya Redis'ten verileri al
        click_data = {}
        if redis_client:
            # Redis'ten tüm keyleri al
            keys = redis_client.keys('clicks:*')
            for key in keys:
                click_data[key] = int(redis_client.get(key))
        else:
            # Memory storage'dan al
            click_data = detector.memory_storage

        # Verileri işle
        total_clicks = sum(click_data.values())
        unique_ips = len(click_data)
        
        return render_template(
            'dashboard.html',
            click_data=click_data,
            total_clicks=total_clicks,
            unique_ips=unique_ips
        )
    except Exception as e:
        logger.error(f"Dashboard hatası: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Global detector instance
detector = ClickFraudDetector()