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

app = Flask(__name__)
CORS(app)

# Redis bağlantısı
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD', None),
    decode_responses=True
)

# E-posta yapılandırması
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)

# Loglama ayarlarını yapılandır
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ClickFraudDetector:
    def __init__(self):
        self.clicks = deque(maxlen=500)
        self.suspicious_activities = deque(maxlen=50)
        self.admin_email = os.getenv('ADMIN_EMAIL')
        self.location_data = []
        self.country_stats = Counter()
        
        # GeoLite2 veritabanını yükle
        try:
            self.geoip_reader = geoip2.database.Reader('GeoLite2-City.mmdb')
        except FileNotFoundError:
            self.geoip_reader = None
            logger.error("GeoLite2 veritabanı bulunamadı")
    
    def get_click_count(self, ip, campaign_id=None):
        """Redis'ten IP için tıklama sayısını al"""
        key = f"clicks:{ip}"
        if campaign_id:
            key += f":{campaign_id}"
        
        clicks = redis_client.get(key)
        return int(clicks) if clicks else 0

    def increment_click_count(self, ip, campaign_id=None):
        """Redis'te IP için tıklama sayısını artır"""
        key = f"clicks:{ip}"
        if campaign_id:
            key += f":{campaign_id}"
            
        # 1 saat geçerli olacak şekilde artır
        redis_client.incr(key)
        redis_client.expire(key, 3600)  # 1 saat

    def is_bot_activity(self, user_agent, ip):
        """Bot aktivitesi kontrolü"""
        if not user_agent:
            return True
            
        user_agent = user_agent.lower()
        suspicious_terms = ['bot', 'crawler', 'spider', 'http', 'python', 'curl']
        
        # User-Agent kontrolü
        if any(term in user_agent for term in suspicious_terms):
            return True
            
        # Hız kontrolü
        last_click_key = f"last_click:{ip}"
        last_click = redis_client.get(last_click_key)
        
        if last_click:
            time_diff = time.time() - float(last_click)
            if time_diff < 2:  # 2 saniyeden kısa sürede tekrar tıklama
                return True
                
        redis_client.set(last_click_key, time.time(), ex=3600)
        return False

    def check_click(self, ip, campaign_id, user_agent):
        """Tıklama kontrolü"""
        try:
            # Bot kontrolü
            if self.is_bot_activity(user_agent, ip):
                logger.warning(f"Bot aktivitesi tespit edildi: {ip}")
                return False, "Bot aktivitesi tespit edildi"

            # Tıklama sayısı kontrolü
            click_count = self.get_click_count(ip, campaign_id)
            
            if click_count >= 5:  # 1 saatte en fazla 5 tıklama
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
    gclid = request.args.get('gclid')
    campaign_id = request.args.get('utm_campaign', 'default')
    ip = request.remote_addr or request.headers.get('X-Forwarded-For', '').split(',')[0]
    user_agent = request.headers.get('User-Agent', '')

    # Tıklama kontrolü
    is_valid, reason = detector.check_click(ip, campaign_id, user_agent)

    if not is_valid:
        return redirect('https://servisimonline.com/bot-saldirisi.html')

    # Normal sayfa gösterimi
    return render_template('index.html')

@app.route('/bot-saldirisi.html')
def bot_page():
    """Bot sayfası"""
    return render_template('bot-saldirisi.html')

# Global detector instance
detector = ClickFraudDetector()