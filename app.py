from flask import Flask, jsonify, request, render_template, send_file
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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from expiringdict import ExpiringDict
import re

app = Flask(__name__)
CORS(app)

# Rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Cache configuration
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})

# E-posta yapılandırması
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global değişkenler
last_activity_time = datetime.now()
INACTIVITY_THRESHOLD = 600  # 10 dakika
BLOCK_DURATION = 3600  # 1 saat
MAX_VIEWS_PER_IP = 5
SUSPICIOUS_COUNTRIES = {'CountryA', 'CountryB', 'CountryC'}
BOT_PATTERNS = [
    'bot', 'crawler', 'spider', 'headless',
    'python', 'curl', 'wget', 'phantom',
    'selenium', 'chrome-headless'
]

class ClickFraudDetector:
    def __init__(self):
        self.clicks = deque(maxlen=5000)
        self.suspicious_activities = deque(maxlen=1000)
        self.sessions = ExpiringDict(max_len=10000, max_age_seconds=3600)
        self.blocked_ips = ExpiringDict(max_len=10000, max_age_seconds=BLOCK_DURATION)
        self.ip_request_count = ExpiringDict(max_len=10000, max_age_seconds=3600)
        self.admin_email = os.getenv('ADMIN_EMAIL')
        self.location_data = deque(maxlen=1000)
        self.country_stats = Counter()
        
        # GeoLite2 veritabanını yükle
        try:
            self.geoip_reader = geoip2.database.Reader('GeoLite2-City.mmdb')
            logger.info("GeoIP veritabanı başarıyla yüklendi")
        except FileNotFoundError:
            logger.error("GeoLite2 veritabanı bulunamadı - Konum kontrolü devre dışı")
            self.geoip_reader = None
    
    def is_ip_blocked(self, ip):
        """IP'nin bloklu olup olmadığını kontrol et"""
        return ip in self.blocked_ips
    
    def block_ip(self, ip, reason):
        """IP'yi blokla"""
        self.blocked_ips[ip] = {
            'timestamp': datetime.now(),
            'reason': reason
        }
        logger.warning(f"IP bloklandı: {ip}, Sebep: {reason}")
    
    def is_suspicious_request(self, request_data):
        """Şüpheli istek kontrolü"""
        # User-Agent kontrolü
        user_agent = request_data.get('user_agent', '').lower()
        if any(pattern in user_agent for pattern in BOT_PATTERNS):
            return True
        
        # Header kontrolü
        headers = request_data.get('headers', {})
        if not headers.get('Accept') or not headers.get('Accept-Language'):
            return True
        
        # Referrer kontrolü
        referrer = headers.get('Referer', '')
        if not referrer or not re.match(r'^https?://', referrer):
            return True
        
        return False
    
    def check_rate_limit(self, ip):
        """Rate limiting kontrolü"""
        current_time = datetime.now()
        if ip not in self.ip_request_count:
            self.ip_request_count[ip] = {'count': 1, 'first_request': current_time}
            return True
        
        request_info = self.ip_request_count[ip]
        request_info['count'] += 1
        
        # Son 1 saatteki istek sayısı kontrolü
        if (current_time - request_info['first_request']).total_seconds() <= 3600:
            if request_info['count'] > 100:  # Saatte 100 istek limiti
                self.block_ip(ip, "Rate limit aşıldı")
                return False
        else:
            # Süre dolmuşsa sayacı sıfırla
            request_info['count'] = 1
            request_info['first_request'] = current_time
        
        return True
    
    def record_click(self, click_data):
        """Geliştirilmiş tıklama kaydı ve kontrol"""
        try:
            ip = click_data.get('ip', 'unknown')
            
            # IP blok kontrolü
            if self.is_ip_blocked(ip):
                return {
                    'success': False,
                    'show_ad': False,
                    'reason': 'IP bloklanmış'
                }
            
            # Rate limit kontrolü
            if not self.check_rate_limit(ip):
                return {
                    'success': False,
                    'show_ad': False,
                    'reason': 'Rate limit aşıldı'
                }
            
            # Şüpheli istek kontrolü
            if self.is_suspicious_request(click_data):
                self.block_ip(ip, "Şüpheli istek paterni")
                return {
                    'success': False,
                    'show_ad': False,
                    'reason': 'Şüpheli istek'
                }
            
            current_time = datetime.now()
            campaign_id = click_data.get('campaign_id', 'unknown')
            session_key = f"{ip}_{campaign_id}"
            
            # Konum kontrolü ve risk skoru hesaplama
            location = self.get_location_from_ip(ip)
            risk_score = self.calculate_risk_score(location, click_data)
            
            if risk_score >= 80:  # Yüksek risk
                self.block_ip(ip, f"Yüksek risk skoru: {risk_score}")
                return {
                    'success': False,
                    'show_ad': False,
                    'reason': 'Yüksek risk'
                }
            
            # Session kontrolü
            if session_key in self.sessions:
                session = self.sessions[session_key]
                if session['click_count'] >= MAX_VIEWS_PER_IP:
                    return {
                        'success': False,
                        'show_ad': False,
                        'reason': 'Görüntüleme limiti aşıldı'
                    }
                
                # Hızlı tıklama kontrolü
                if 'last_click' in session:
                    time_diff = (current_time - session['last_click']).total_seconds()
                    if time_diff < 2:  # 2 saniyeden kısa sürede tıklama
                        session['quick_clicks'] = session.get('quick_clicks', 0) + 1
                        if session['quick_clicks'] >= 3:  # 3 hızlı tıklama = blok
                            self.block_ip(ip, "Çok fazla hızlı tıklama")
                            return {
                                'success': False,
                                'show_ad': False,
                                'reason': 'Hızlı tıklama limiti aşıldı'
                            }
            else:
                self.sessions[session_key] = {
                    'first_click': current_time,
                    'click_count': 0,
                    'quick_clicks': 0
                }
            
            session = self.sessions[session_key]
            session['last_click'] = current_time
            session['click_count'] += 1
            
            # Tıklama kaydı
            click_data.update({
                'timestamp': current_time,
                'location': location,
                'risk_score': risk_score
            })
            self.clicks.append(click_data)
            
            # Yüksek riskli aktivite bildirimi
            if risk_score >= 50:
                self._record_suspicious(click_data, f"Yüksek risk skoru: {risk_score}")
                self.send_alert_email(
                    "Yüksek Riskli Aktivite",
                    f"IP: {ip}\nRisk Skoru: {risk_score}\nKonum: {location['country']}\nZaman: {current_time}"
                )
            
            return {
                'success': True,
                'show_ad': True,
                'risk_score': risk_score
            }
            
        except Exception as e:
            logger.error(f"Tıklama kaydı hatası: {str(e)}")
            return {
                'success': False,
                'show_ad': True,  # Hata durumunda reklamı göster
                'reason': 'Sistem hatası'
            }
    
    def calculate_risk_score(self, location, click_data):
        """Geliştirilmiş risk skoru hesaplama"""
        risk_score = 0
        
        # Konum bazlı risk
        if location['country'] == 'Unknown':
            risk_score += 40
        elif location['country'] in SUSPICIOUS_COUNTRIES:
            risk_score += 30
        
        # User-Agent bazlı risk
        user_agent = click_data.get('user_agent', '').lower()
        if any(pattern in user_agent for pattern in BOT_PATTERNS):
            risk_score += 40
        
        # Header bazlı risk
        headers = click_data.get('headers', {})
        if not headers.get('Accept') or not headers.get('Accept-Language'):
            risk_score += 20
        
        # IP bazlı risk
        ip = click_data.get('ip', 'unknown')
        if ip in self.ip_request_count:
            request_count = self.ip_request_count[ip]['count']
            if request_count > 50:
                risk_score += 30
        
        return min(risk_score, 100)  # Maksimum 100
    
    def _record_suspicious(self, click_data, reason):
        """Geliştirilmiş şüpheli aktivite kaydı"""
        self.suspicious_activities.append({
            'timestamp': datetime.now(),
            'ip': click_data.get('ip'),
            'reason': reason,
            'location': click_data.get('location'),
            'risk_score': click_data.get('risk_score'),
            'user_agent': click_data.get('user_agent')
        })

# ... (Diğer metodlar aynı kalacak)

detector = ClickFraudDetector()

@app.before_request
def before_request():
    """Her istekten önce kontroller"""
    if request.path.startswith('/static'):
        return
    
    ip = request.remote_addr
    
    # IP blok kontrolü
    if detector.is_ip_blocked(ip):
        return jsonify({
            'error': 'IP blocked',
            'reason': detector.blocked_ips[ip]['reason']
        }), 403
    
    # Rate limit kontrolü
    if not detector.check_rate_limit(ip):
        return jsonify({
            'error': 'Rate limit exceeded'
        }), 429

@app.route('/')
@limiter.limit("30 per minute")
def dashboard():
    return render_template('dashboard.html')

@app.route('/check-ad-visibility', methods=['POST'])
@limiter.limit("20 per minute")
def check_ad_visibility():
    try:
        ip = request.remote_addr
        
        # IP blok kontrolü
        if detector.is_ip_blocked(ip):
            return jsonify({
                'show_ad': False,
                'reason': 'IP blocked'
            })
        
        # Diğer kontroller...
        result = detector.record_click({
            'ip': ip,
            'user_agent': request.headers.get('User-Agent'),
            'headers': dict(request.headers),
            'timestamp': datetime.now()
        })
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Kontrol hatası: {str(e)}")
        return jsonify({
            'show_ad': False,
            'reason': 'System error'
        })

@app.route('/record-click', methods=['POST'])
@limiter.limit("20 per minute")
def record_click():
    return jsonify(detector.record_click(request.json))

@app.route('/api/stats')
@limiter.limit("10 per minute")
@cache.cached(timeout=60)
def get_stats():
    return jsonify(detector.get_stats())

@app.route('/api/quick-exit-report')
@limiter.limit("10 per minute")
@cache.cached(timeout=60)
def get_quick_exit_report():
    return jsonify(detector.get_quick_exit_report())

@app.route('/api/suspicious-activities')
@limiter.limit("10 per minute")
@cache.cached(timeout=60)
def get_suspicious_activities():
    return jsonify(list(detector.suspicious_activities))

if __name__ == '__main__':
    app.run(debug=False) 