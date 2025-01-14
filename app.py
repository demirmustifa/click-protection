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

app = Flask(__name__)
CORS(app)

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

# Global değişkenler
last_activity_time = datetime.now()
INACTIVITY_THRESHOLD = 600  # 10 dakika

@app.before_request
def before_request():
    """Her istekte son aktivite zamanını güncelle"""
    global last_activity_time
    last_activity_time = datetime.now()

def keep_alive():
    """Basit ping servisi"""
    global last_activity_time
    
    while True:
        try:
            time.sleep(30)
            current_time = datetime.now()
            
            if (current_time - last_activity_time).total_seconds() >= INACTIVITY_THRESHOLD:
                try:
                    requests.head(
                        "https://click-protection.onrender.com/",
                        timeout=5,
                        headers={'User-Agent': 'ClickProtection-Ping/1.0'}
                    )
                    last_activity_time = current_time
                except:
                    pass
        except:
            time.sleep(60)

# Ping servisini başlat
if os.environ.get('RENDER') == 'true':
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    logger.info("Ping servisi başlatıldı")

class ClickFraudDetector:
    def __init__(self):
        self.clicks = deque(maxlen=500)
        self.suspicious_activities = deque(maxlen=50)
        self.sessions = {}
        self.admin_email = os.getenv('ADMIN_EMAIL')
        self.location_data = []
        self.country_stats = Counter()
        self.seen_ips = defaultdict(set)  # IP'lerin hangi kampanyalara tıkladığını tutacak
        
        # GeoLite2 veritabanını yükle
        try:
            self.geoip_reader = geoip2.database.Reader('GeoLite2-City.mmdb')
        except FileNotFoundError:
            self.geoip_reader = None
            logger.error("GeoLite2 veritabanı bulunamadı")
    
    def should_show_ad(self, ip, campaign_id):
        """IP'nin bu kampanyayı daha önce görüp görmediğini kontrol et"""
        return campaign_id not in self.seen_ips[ip]
    
    def record_ad_view(self, ip, campaign_id):
        """IP'nin kampanyayı gördüğünü kaydet"""
        self.seen_ips[ip].add(campaign_id)
        return True
    
    def get_location_from_ip(self, ip):
        """IP adresinden konum bilgisi alma"""
        try:
            if self.geoip_reader and ip != 'unknown':
                response = self.geoip_reader.city(ip)
                location = {
                    'ip': ip,
                    'country': response.country.name,
                    'city': response.city.name,
                    'latitude': response.location.latitude,
                    'longitude': response.location.longitude,
                    'risk_score': 0  # Risk skoru başlangıçta 0
                }
                return location
        except AddressNotFoundError:
            logger.warning(f"IP adresi bulunamadı: {ip}")
        except Exception as e:
            logger.error(f"Konum tespiti hatası: {str(e)}")
        
        return {
            'ip': ip,
            'country': 'Unknown',
            'city': 'Unknown',
            'latitude': 0,
            'longitude': 0,
            'risk_score': 0
        }
    
    def send_alert_email(self, subject, body):
        """Şüpheli aktivite e-posta bildirimi"""
        try:
            if self.admin_email:
                msg = Message(
                    subject,
                    recipients=[self.admin_email],
                    body=body
                )
                mail.send(msg)
                logger.info(f"Alert email sent: {subject}")
        except Exception as e:
            logger.error(f"Email sending error: {str(e)}")
    
    def record_click(self, click_data):
        """Tıklama kaydı ve konum analizi"""
        try:
            current_time = datetime.now()
            ip = click_data.get('ip', 'unknown')
            campaign_id = click_data.get('campaign_id', 'unknown')
            
            # Bu IP bu kampanyayı daha önce görmüş mü kontrol et
            if not self.should_show_ad(ip, campaign_id):
                logger.info(f"IP {ip} daha önce kampanya {campaign_id}'yi görmüş, reklam gösterilmeyecek")
                return {
                    'success': False,
                    'show_ad': False,
                    'reason': 'IP daha önce bu reklamı görmüş'
                }
            
            # IP'nin bu kampanyayı gördüğünü kaydet
            self.record_ad_view(ip, campaign_id)
            
            # Mevcut tıklama işlemleri...
            location = self.get_location_from_ip(ip)
            click_data['location'] = location
            
            if location['country'] != 'Unknown':
                self.country_stats[location['country']] += 1
            
            risk_score = 0
            if location['country'] in ['Unknown', None]:
                risk_score += 50
            
            high_risk_countries = ['CountryA', 'CountryB']
            if location['country'] in high_risk_countries:
                risk_score += 30
            
            location['risk_score'] = risk_score
            
            self.location_data.append({
                'timestamp': current_time,
                'location': location,
                'risk_score': risk_score
            })
            
            session_key = f"{ip}_{campaign_id}"
            
            if session_key not in self.sessions:
                self.sessions[session_key] = {
                    'first_click': current_time,
                    'click_count': 0,
                    'quick_exits': 0,
                    'country': location['country']
                }
            
            session = self.sessions[session_key]
            
            if 'last_click' in session:
                time_diff = (current_time - session['last_click']).total_seconds()
                if time_diff < 3:
                    session['quick_exits'] += 1
                    risk_score += 20
                    if session['quick_exits'] >= 5:
                        self._record_suspicious(click_data, "Çok sayıda hızlı çıkış")
                        self.send_alert_email(
                            "Şüpheli Aktivite Tespit Edildi",
                            f"IP: {ip}\nÜlke: {location['country']}\nŞehir: {location['city']}\nNeden: Çok sayıda hızlı çıkış\nZaman: {current_time}"
                        )
            
            if self._is_bot(click_data.get('user_agent', '')):
                risk_score += 40
                self._record_suspicious(click_data, "Bot aktivitesi")
                self.send_alert_email(
                    "Bot Aktivitesi Tespit Edildi",
                    f"IP: {ip}\nÜlke: {location['country']}\nŞehir: {location['city']}\nUser-Agent: {click_data.get('user_agent')}\nZaman: {current_time}"
                )
            
            session['last_click'] = current_time
            session['click_count'] = min(session['click_count'] + 1, 100)
            
            click_data['timestamp'] = current_time
            click_data['risk_score'] = risk_score
            self.clicks.append(click_data)
            
            return {
                'success': True,
                'show_ad': True,
                'risk_score': risk_score
            }
            
        except Exception as e:
            logger.error(f"Tıklama kaydı hatası: {str(e)}")
            return {
                'success': False,
                'show_ad': False,
                'reason': 'Sistem hatası'
            }
    
    def _is_bot(self, user_agent):
        """Basit bot kontrolü"""
        user_agent = user_agent.lower()
        return any(x in user_agent for x in ['bot', 'crawler', 'spider'])
    
    def _record_suspicious(self, click_data, reason):
        """Şüpheli aktivite kaydı"""
        self.suspicious_activities.append({
            'timestamp': datetime.now(),
            'ip': click_data.get('ip'),
            'reason': reason
        })
    
    def get_stats(self):
        """Basit istatistikler"""
        suspicious_count = len(self.suspicious_activities)
        total_clicks = len(self.clicks)
        return {
            'total_clicks': total_clicks,
            'suspicious_clicks': suspicious_count,
            'session_count': len(self.sessions)
        }
    
    def get_quick_exit_report(self):
        """Hızlı çıkış raporu"""
        report = {
            'total_sessions': len(self.sessions),
            'suspicious_sessions': sum(1 for s in self.sessions.values() if s.get('quick_exits', 0) >= 5),
            'quick_exits_total': sum(s.get('quick_exits', 0) for s in self.sessions.values())
        }
        return report
    
    def generate_excel_report(self):
        """Excel raporu oluşturma"""
        try:
            df = pd.DataFrame(list(self.clicks))
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Tıklama Verileri', index=False)
            output.seek(0)
            return output
        except Exception as e:
            logger.error(f"Excel rapor oluşturma hatası: {str(e)}")
            return None
    
    def generate_pdf_report(self):
        """PDF raporu oluşturma"""
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []

            # İstatistikler
            stats = self.get_stats()
            data = [
                ['Metrik', 'Değer'],
                ['Toplam Tıklama', stats['total_clicks']],
                ['Şüpheli Tıklama', stats['suspicious_clicks']],
                ['Oturum Sayısı', stats['session_count']]
            ]

            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
            doc.build(elements)
            buffer.seek(0)
            return buffer
        except Exception as e:
            logger.error(f"PDF rapor oluşturma hatası: {str(e)}")
            return None
    
    def get_location_stats(self):
        """Konum istatistiklerini getir"""
        try:
            stats = {
                'country_stats': dict(self.country_stats),
                'recent_locations': [
                    {
                        'latitude': loc['location']['latitude'],
                        'longitude': loc['location']['longitude'],
                        'risk_score': loc['risk_score'],
                        'country': loc['location']['country'],
                        'city': loc['location']['city']
                    }
                    for loc in self.location_data[-100:]  # Son 100 konum
                ],
                'high_risk_locations': [
                    {
                        'latitude': loc['location']['latitude'],
                        'longitude': loc['location']['longitude'],
                        'risk_score': loc['risk_score'],
                        'country': loc['location']['country'],
                        'city': loc['location']['city']
                    }
                    for loc in self.location_data
                    if loc['risk_score'] > 50  # Yüksek riskli lokasyonlar
                ]
            }
            return stats
        except Exception as e:
            logger.error(f"Konum istatistikleri hatası: {str(e)}")
            return {}

detector = ClickFraudDetector()

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/check-ad-visibility', methods=['POST'])
def check_ad_visibility():
    """Reklamın gösterilip gösterilmeyeceğini kontrol et"""
    try:
        ip = request.remote_addr or request.headers.get('X-Forwarded-For', '').split(',')[0]
        
        # IP'nin görüntüleme sayısını kontrol et
        if ip not in detector.seen_ips:
            detector.seen_ips[ip] = set(['first_view'])
            click_count = 1
            logger.info(f"İlk görüntüleme: {ip}")
        else:
            click_count = len(detector.seen_ips[ip])
            logger.info(f"Görüntüleme sayısı {click_count}: {ip}")
        
        # 2'den fazla görüntülemede engelle
        if click_count >= 2:
            logger.warning(f"IP limiti aşıldı: {ip}")
            return jsonify({
                'show_ad': False,
                'redirect': 'https://servisimonline.com/bot-saldirisi.html',
                'reason': 'IP limiti aşıldı',
                'click_count': click_count
            })
        
        # IP'nin görüntüleme sayısını artır
        detector.seen_ips[ip].add(f'view_{click_count + 1}')
        
        # IP'nin konum bilgilerini al ve kaydet
        location = detector.get_location_from_ip(ip)
        detector.location_data.append({
            'timestamp': datetime.now(),
            'location': location,
            'risk_score': click_count * 25  # Her görüntülemede risk skoru artar
        })
        
        if location['country'] != 'Unknown':
            detector.country_stats[location['country']] += 1
        
        return jsonify({
            'show_ad': True,
            'reason': f'{click_count}. gösterim',
            'click_count': click_count
        })
    except Exception as e:
        logger.error(f"Kontrol hatası: {str(e)}")
        return jsonify({
            'show_ad': True,
            'reason': 'Hata durumunda göster'
        })

@app.route('/record-click', methods=['POST'])
def record_click():
    """Tıklama kaydı ve reklam gösterim kontrolü"""
    result = detector.record_click(request.json)
    return jsonify(result)

@app.route('/api/stats')
def get_stats():
    return jsonify(detector.get_stats())

@app.route('/api/quick-exit-report')
def get_quick_exit_report():
    return jsonify(detector.get_quick_exit_report())

@app.route('/api/suspicious-activities')
def get_suspicious_activities():
    return jsonify(list(detector.suspicious_activities))

@app.route('/api/location-stats')
def get_location_stats():
    """Konum istatistiklerini döndür"""
    return jsonify(detector.get_location_stats())

@app.route('/download-excel')
def download_excel():
    """Excel raporu indirme"""
    output = detector.generate_excel_report()
    if output:
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'click_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    return jsonify({'error': 'Rapor oluşturulamadı'}), 500

@app.route('/download-pdf')
def download_pdf():
    """PDF raporu indirme"""
    buffer = detector.generate_pdf_report()
    if buffer:
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'click_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        )
    return jsonify({'error': 'Rapor oluşturulamadı'}), 500

if __name__ == '__main__':
    app.run(debug=True) 