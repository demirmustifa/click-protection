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
        self.memory_storage = {}
        self.click_timestamps = defaultdict(list)  # IP bazlı timestamp takibi
        
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
                return len(self.click_timestamps[key])
        except:
            key = f"{ip}:{campaign_id}" if campaign_id else ip
            return len(self.click_timestamps[key])

    def increment_click_count(self, ip, campaign_id=None):
        """IP için tıklama sayısını artır ve timestamp'i kaydet"""
        try:
            current_time = time.time()
            key = f"{ip}:{campaign_id}" if campaign_id else ip
            
            # Son 1 saatlik tıklamaları tut
            self.click_timestamps[key] = [ts for ts in self.click_timestamps[key] 
                                        if current_time - ts < 3600]
            self.click_timestamps[key].append(current_time)
            
            if redis_client:
                redis_key = f"clicks:{key}"
                redis_client.incr(redis_key)
                redis_client.expire(redis_key, 3600)
        except Exception as e:
            logger.error(f"Tıklama artırma hatası: {str(e)}")

    def check_click(self, ip, campaign_id, user_agent):
        """Gelişmiş tıklama kontrolü"""
        try:
            current_time = time.time()
            key = f"{ip}:{campaign_id}" if campaign_id else ip
            
            # Son 24 saatteki tıklamaları temizle
            self.click_timestamps[key] = [ts for ts in self.click_timestamps[key] 
                                        if current_time - ts < 86400]  # 24 saat
            
            # Toplam tıklama sayısı kontrolü (24 saat içinde)
            click_count = len(self.click_timestamps[key])
            
            # Son 1 dakikadaki tıklama sayısı
            recent_clicks = len([ts for ts in self.click_timestamps[key] 
                               if current_time - ts < 60])  # 1 dakika
            
            logger.info(f"IP: {ip}, 24 saat içinde toplam: {click_count}, Son 1dk: {recent_clicks}")
            
            # Bot kontrolü kuralları
            if click_count >= 5:  # 24 saat içinde max 5 tıklama
                logger.warning(f"24 saat limit aşımı: {ip}")
                return False, "24 saat içinde çok fazla tıklama"
                
            if recent_clicks >= 2:  # 1 dakika içinde max 2 tıklama
                logger.warning(f"Hız limiti aşımı: {ip}")
                return False, "Çok hızlı tıklama"
            
            # Bot kontrolleri
            if not user_agent:
                return False, "Geçersiz istek"
                
            user_agent_lower = user_agent.lower()
            if any(bot in user_agent_lower for bot in ['bot', 'crawler', 'spider', 'headless']):
                logger.warning(f"Bot user-agent tespiti: {ip}")
                return False, "Bot tespit edildi"
            
            # Tıklama sayısını artır
            self.increment_click_count(ip, campaign_id)
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Tıklama kontrolü hatası: {str(e)}")
            return False, "Sistem hatası"

@app.route('/')
def index():
    """Ana sayfa yönlendirmesi"""
    try:
        gclid = request.args.get('gclid')
        campaign_id = request.args.get('utm_campaign', 'default')
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
        user_agent = request.headers.get('User-Agent', '')

        # Tıklama kontrolü
        is_valid, reason = detector.check_click(ip, campaign_id, user_agent)
        logger.info(f"Kontrol sonucu: {is_valid}, {reason}")

        if not is_valid:
            return render_template('bot-saldirisi.html')

        if not gclid:
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
        # Tıklama verilerini al
        click_data = {}
        if redis_client:
            keys = redis_client.keys('clicks:*')
            for key in keys:
                click_data[key.replace('clicks:', '')] = int(redis_client.get(key))
        else:
            for key, timestamps in detector.click_timestamps.items():
                click_data[key] = len(timestamps)

        # İstatistikleri hesapla
        total_clicks = sum(click_data.values())
        unique_ips = len(click_data)
        
        # Ülke bazlı istatistikler
        country_stats = Counter()
        try:
            with geoip2.database.Reader('GeoLite2-Country.mmdb') as reader:
                for ip in click_data.keys():
                    try:
                        if ',' in ip:
                            ip = ip.split(',')[0].strip()
                        response = reader.country(ip)
                        country_stats[response.country.name] += click_data[ip]
                    except:
                        country_stats['Bilinmeyen'] += click_data[ip]
        except:
            country_stats['Bilinmeyen'] = total_clicks

        return render_template(
            'dashboard.html',
            click_data=click_data,
            total_clicks=total_clicks,
            unique_ips=unique_ips,
            country_stats=dict(country_stats)
        )
    except Exception as e:
        logger.error(f"Dashboard hatası: {str(e)}")
        return f"Dashboard hatası: {str(e)}", 500  # Hatayı göster

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Statik dosyaları serve et"""
    return send_file(f'static/{filename}')

# Global detector instance
detector = ClickFraudDetector()