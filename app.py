from flask import Flask, jsonify, request, render_template
from datetime import datetime, timedelta
import logging
import json
from collections import deque
import threading
import time
import requests
import os

app = Flask(__name__)

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
        self.clicks = deque(maxlen=500)  # Daha az tıklama sakla
        self.suspicious_activities = deque(maxlen=50)
        self.sessions = {}
        
    def record_click(self, click_data):
        """Basitleştirilmiş tıklama kaydı"""
        try:
            current_time = datetime.now()
            ip = click_data.get('ip', 'unknown')
            session_key = f"{ip}_{click_data.get('campaign_id', 'unknown')}"
            
            # Oturum bilgilerini güncelle
            if session_key not in self.sessions:
                self.sessions[session_key] = {
                    'first_click': current_time,
                    'click_count': 0,
                    'quick_exits': 0
                }
            
            session = self.sessions[session_key]
            
            # Hızlı çıkış kontrolü
            if 'last_click' in session:
                time_diff = (current_time - session['last_click']).total_seconds()
                if time_diff < 3:
                    session['quick_exits'] += 1
                    if session['quick_exits'] >= 5:  # 5 hızlı çıkış şüpheli
                        self._record_suspicious(click_data, "Çok sayıda hızlı çıkış")
            
            # Bot kontrolü
            if self._is_bot(click_data.get('user_agent', '')):
                self._record_suspicious(click_data, "Bot aktivitesi")
            
            # Verileri güncelle
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

if __name__ == '__main__':
    app.run(debug=True) 