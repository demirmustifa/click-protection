from flask import Flask, jsonify, request, render_template
from datetime import datetime, timedelta
import pandas as pd
from sklearn.ensemble import IsolationForest
import logging
import json
from collections import deque
import threading
import time
import requests
import os
import signal

app = Flask(__name__)

# Loglama ayarlarını yapılandır
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global değişkenler
ping_thread = None
should_run = True

def signal_handler(signum, frame):
    """Sinyal yakalayıcı"""
    global should_run
    logger.info(f"Sinyal alındı: {signum}")
    should_run = False

# Sinyalleri yakala
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def keep_alive():
    """Basit ping servisi"""
    while True:
        try:
            response = requests.get(
                "https://click-protection.onrender.com/api/stats",
                timeout=5
            )
            logger.info(f"Ping durumu: {response.status_code}")
        except Exception as e:
            logger.error(f"Ping hatası: {str(e)}")
        
        time.sleep(180)  # 3 dakika bekle

# Ping servisini başlat
if os.environ.get('RENDER') == 'true':
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    logger.info("Ping servisi başlatıldı")

class ClickFraudDetector:
    def __init__(self):
        self.clicks = deque(maxlen=10000)  # Son 10000 tıklamayı sakla
        self.suspicious_activities = deque(maxlen=100)  # Son 100 şüpheli aktiviteyi sakla
        self.sessions = {}  # Oturum bilgilerini sakla
        self.lock = threading.Lock()
        
        # Periyodik model eğitimi için thread başlat
        self.model = None
        self.training_thread = threading.Thread(target=self._periodic_training)
        self.training_thread.daemon = True
        self.training_thread.start()

    def _periodic_training(self):
        """Her saat başı modeli yeniden eğit"""
        while True:
            time.sleep(3600)  # 1 saat bekle
            with self.lock:
                if len(self.clicks) > 100:  # En az 100 tıklama varsa
                    self._train_model()

    def _train_model(self):
        """Mevcut verilerle modeli eğit"""
        if len(self.clicks) < 100:
            return
        
        # Tıklama verilerinden özellikler çıkar
        features = []
        for click in self.clicks:
            session_key = f"{click['ip']}_{click.get('campaign_id', 'unknown')}"
            session = self.sessions.get(session_key, {})
            
            features.append([
                session.get('click_count', 0),
                session.get('quick_exits', 0),
                (session.get('quick_exits', 0) / session.get('click_count', 1)) if session.get('click_count', 0) > 0 else 0
            ])
        
        # Modeli eğit
        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.model.fit(features)

    def _is_bot(self, user_agent):
        """Kullanıcı ajanının bot olup olmadığını kontrol et"""
        bot_patterns = ['bot', 'crawler', 'spider', 'headless']
        user_agent = user_agent.lower()
        return any(pattern in user_agent for pattern in bot_patterns)

    def record_click(self, click_data):
        with self.lock:
            current_time = datetime.now()
            ip = click_data.get('ip', 'unknown')
            
            # Oturum kontrolü
            session_key = f"{ip}_{click_data.get('campaign_id', 'unknown')}"
            session = self.sessions.get(session_key, {
                'first_click': current_time,
                'last_click': current_time,
                'click_count': 0,
                'quick_exits': 0
            })
            
            # Hızlı çıkış kontrolü (3 saniyeden az)
            if session['click_count'] > 0:
                time_diff = (current_time - session['last_click']).total_seconds()
                if time_diff < 3:
                    session['quick_exits'] += 1
                    self._record_suspicious_activity(click_data, "Hızlı çıkış tespit edildi", time_diff)
            
            session['last_click'] = current_time
            session['click_count'] += 1
            self.sessions[session_key] = session
            
            # Tıklama verisini kaydet
            click_data['timestamp'] = current_time
            click_data['session_data'] = {
                'quick_exits': session['quick_exits'],
                'total_clicks': session['click_count']
            }
            self.clicks.append(click_data)
            
            # Şüpheli aktivite kontrolü
            is_suspicious = self._analyze_click(click_data, session)
            return not is_suspicious

    def _analyze_click(self, click_data, session):
        is_suspicious = False
        
        # Hızlı çıkış oranı kontrolü
        if session['click_count'] > 5 and (session['quick_exits'] / session['click_count']) > 0.5:
            self._record_suspicious_activity(
                click_data,
                "Yüksek hızlı çıkış oranı",
                f"{session['quick_exits']}/{session['click_count']} tıklama"
            )
            is_suspicious = True
        
        # Bot kontrolü
        if self._is_bot(click_data['user_agent']):
            self._record_suspicious_activity(click_data, "Bot aktivitesi tespit edildi")
            is_suspicious = True
        
        return is_suspicious

    def _record_suspicious_activity(self, click_data, reason, details=None):
        suspicious_activity = {
            'timestamp': datetime.now(),
            'ip': click_data.get('ip', 'unknown'),
            'reason': reason,
            'details': details,
            'campaign_id': click_data.get('campaign_id', 'unknown'),
            'user_agent': click_data.get('user_agent', 'unknown')
        }
        self.suspicious_activities.append(suspicious_activity)

    def get_quick_exit_report(self):
        with self.lock:
            report = {
                'total_sessions': len(self.sessions),
                'suspicious_sessions': 0,
                'quick_exits_total': 0,
                'detailed_sessions': []
            }
            
            for session_key, session in self.sessions.items():
                quick_exit_rate = session['quick_exits'] / session['click_count'] if session['click_count'] > 0 else 0
                session_data = {
                    'session_id': session_key,
                    'total_clicks': session['click_count'],
                    'quick_exits': session['quick_exits'],
                    'quick_exit_rate': quick_exit_rate,
                    'first_click': session['first_click'].isoformat(),
                    'last_click': session['last_click'].isoformat(),
                    'risk_level': self._calculate_risk_level(quick_exit_rate)
                }
                
                if quick_exit_rate > 0.3:  # %30'dan fazla hızlı çıkış varsa şüpheli
                    report['suspicious_sessions'] += 1
                
                report['quick_exits_total'] += session['quick_exits']
                report['detailed_sessions'].append(session_data)
            
            return report

    def _calculate_risk_level(self, quick_exit_rate):
        if quick_exit_rate < 0.2:
            return 'Düşük'
        elif quick_exit_rate < 0.5:
            return 'Orta'
        else:
            return 'Yüksek'

    def get_stats(self):
        with self.lock:
            total_clicks = len(self.clicks)
            suspicious_clicks = len(self.suspicious_activities)
            quick_exit_report = self.get_quick_exit_report()
            
            return {
                'total_clicks': total_clicks,
                'suspicious_clicks': suspicious_clicks,
                'quick_exit_total': quick_exit_report['quick_exits_total'],
                'suspicious_sessions': quick_exit_report['suspicious_sessions']
            }

detector = ClickFraudDetector()

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/record-click', methods=['POST'])
def record_click():
    click_data = request.json
    success = detector.record_click(click_data)
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