from flask import Flask, jsonify, request, render_template, send_file
from datetime import datetime, timedelta
import logging
import json
from collections import deque
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

app = Flask(__name__)

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
        """Tıklama kaydı ve şüpheli durum tespiti"""
        try:
            current_time = datetime.now()
            ip = click_data.get('ip', 'unknown')
            session_key = f"{ip}_{click_data.get('campaign_id', 'unknown')}"
            
            if session_key not in self.sessions:
                self.sessions[session_key] = {
                    'first_click': current_time,
                    'click_count': 0,
                    'quick_exits': 0
                }
            
            session = self.sessions[session_key]
            
            # Hızlı çıkış kontrolü ve bildirimi
            if 'last_click' in session:
                time_diff = (current_time - session['last_click']).total_seconds()
                if time_diff < 3:
                    session['quick_exits'] += 1
                    if session['quick_exits'] >= 5:
                        self._record_suspicious(click_data, "Çok sayıda hızlı çıkış")
                        self.send_alert_email(
                            "Şüpheli Aktivite Tespit Edildi",
                            f"IP: {ip}\nNeden: Çok sayıda hızlı çıkış\nZaman: {current_time}"
                        )
            
            # Bot kontrolü ve bildirimi
            if self._is_bot(click_data.get('user_agent', '')):
                self._record_suspicious(click_data, "Bot aktivitesi")
                self.send_alert_email(
                    "Bot Aktivitesi Tespit Edildi",
                    f"IP: {ip}\nUser-Agent: {click_data.get('user_agent')}\nZaman: {current_time}"
                )
            
            session['last_click'] = current_time
            session['click_count'] = min(session['click_count'] + 1, 100)
            
            click_data['timestamp'] = current_time
            self.clicks.append(click_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Tıklama kaydı hatası: {str(e)}")
            return False
    
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

detector = ClickFraudDetector()

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/record-click', methods=['POST'])
def record_click():
    success = detector.record_click(request.json)
    return jsonify({'success': success})

@app.route('/api/stats')
def get_stats():
    return jsonify(detector.get_stats())

@app.route('/api/quick-exit-report')
def get_quick_exit_report():
    return jsonify(detector.get_quick_exit_report())

@app.route('/api/suspicious-activities')
def get_suspicious_activities():
    return jsonify(list(detector.suspicious_activities))

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