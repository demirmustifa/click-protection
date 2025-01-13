from flask import Flask, jsonify, request, render_template
from datetime import datetime, timedelta
import pandas as pd
from sklearn.ensemble import IsolationForest
import logging
from ip_checker import IPChecker
import json
from collections import deque
import threading
import time

app = Flask(__name__)

# Loglama ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClickFraudDetector:
    def __init__(self):
        self.model = IsolationForest(contamination=0.1)
        self.click_data = deque(maxlen=10000)  # Son 10000 tıklamayı tut
        self.suspicious_activities = deque(maxlen=100)  # Son 100 şüpheli aktivite
        self.ip_checker = IPChecker()
        self.lock = threading.Lock()
        
        # Periyodik model eğitimi için thread başlat
        self.training_thread = threading.Thread(target=self._periodic_training)
        self.training_thread.daemon = True
        self.training_thread.start()
    
    def _periodic_training(self):
        """Periyodik olarak modeli yeniden eğit"""
        while True:
            time.sleep(3600)  # Her saat başı
            with self.lock:
                if len(self.click_data) > 100:
                    self._train_model()
    
    def _train_model(self):
        """Modeli mevcut verilerle eğit"""
        if len(self.click_data) < 100:
            return
            
        df = pd.DataFrame(list(self.click_data))
        features = self._extract_features(df)
        self.model.fit(features)
    
    def _extract_features(self, df):
        """Özellik çıkarımı"""
        # Zamansal özellikler
        df['hour'] = df['timestamp'].apply(lambda x: x.hour)
        df['minute'] = df['timestamp'].apply(lambda x: x.minute)
        
        # IP bazlı özellikler
        ip_counts = df['ip'].value_counts()
        df['ip_frequency'] = df['ip'].map(ip_counts)
        
        return df[['hour', 'minute', 'ip_frequency']]
    
    def record_click(self, click_info):
        """Tıklama bilgilerini kaydet ve analiz et"""
        click_data = {
            'ip': click_info.get('ip'),
            'timestamp': datetime.now(),
            'user_agent': click_info.get('user_agent'),
            'referrer': click_info.get('referrer'),
            'campaign_id': click_info.get('campaign_id')
        }
        
        with self.lock:
            self.click_data.append(click_data)
            result = self.analyze_click(click_data)
            
            if result['is_fraudulent']:
                self.suspicious_activities.append({
                    'ip': click_data['ip'],
                    'timestamp': click_data['timestamp'].isoformat(),
                    'reason': result['reason']
                })
            
            return result
    
    def analyze_click(self, click_data):
        """Tıklamanın şüpheli olup olmadığını analiz et"""
        # IP kontrolü
        ip_check = self.ip_checker.check_ip(click_data['ip'])
        if ip_check['is_suspicious']:
            return {'is_fraudulent': True, 'reason': f"Şüpheli IP (Güven Skoru: {ip_check['confidence_score']})"}
        
        # Bot kontrolü
        if self._is_bot_user_agent(click_data['user_agent']):
            return {'is_fraudulent': True, 'reason': 'Bot kullanıcı ajanı tespit edildi'}
        
        # Anomali tespiti
        if len(self.click_data) > 100:
            features = self._extract_features(pd.DataFrame([click_data]))
            prediction = self.model.predict(features)
            if prediction[0] == -1:
                return {'is_fraudulent': True, 'reason': 'Anormal tıklama davranışı'}
        
        return {'is_fraudulent': False, 'reason': 'Geçerli tıklama'}
    
    def _is_bot_user_agent(self, user_agent):
        """Kullanıcı ajanının bot olup olmadığını kontrol et"""
        suspicious_keywords = ['bot', 'crawler', 'spider', 'scraper']
        return any(keyword in user_agent.lower() for keyword in suspicious_keywords)
    
    def get_stats(self):
        """İstatistikleri getir"""
        total_clicks = len(self.click_data)
        suspicious_clicks = len(self.suspicious_activities)
        
        return {
            'total_clicks': total_clicks,
            'suspicious_clicks': suspicious_clicks,
            'last_update': datetime.now().isoformat()
        }

# Global detector instance
detector = ClickFraudDetector()

@app.route('/')
def dashboard():
    """Dashboard sayfası"""
    return render_template('dashboard.html')

@app.route('/api/chart-data')
def chart_data():
    """Grafik verilerini getir"""
    now = datetime.now()
    labels = [(now - timedelta(minutes=i)).strftime('%H:%M') for i in range(30)][::-1]
    
    valid_clicks = []
    suspicious_clicks = []
    
    for label in labels:
        hour, minute = map(int, label.split(':'))
        valid_count = 0
        suspicious_count = 0
        
        for click in detector.click_data:
            if click['timestamp'].hour == hour and click['timestamp'].minute == minute:
                if any(s['timestamp'].startswith(click['timestamp'].isoformat()[:16]) 
                      for s in detector.suspicious_activities):
                    suspicious_count += 1
                else:
                    valid_count += 1
        
        valid_clicks.append(valid_count)
        suspicious_clicks.append(suspicious_count)
    
    return jsonify({
        'labels': labels,
        'valid_clicks': valid_clicks,
        'suspicious_clicks': suspicious_clicks
    })

@app.route('/api/suspicious-activities')
def suspicious_activities():
    """Son şüpheli aktiviteleri getir"""
    return jsonify({
        'activities': list(detector.suspicious_activities)
    })

@app.route('/record-click', methods=['POST'])
def record_click():
    """Tıklama kaydı endpoint'i"""
    click_info = request.json
    result = detector.record_click(click_info)
    return jsonify(result)

@app.route('/stats', methods=['GET'])
def get_stats():
    """İstatistik endpoint'i"""
    return jsonify(detector.get_stats())

if __name__ == '__main__':
    app.run(debug=True) 