from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import user_agents
import geoip2.database
from config import Config
import os

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Veritabanı modelleri
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Visitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.String(200))
    device_type = db.Column(db.String(50))
    browser = db.Column(db.String(50))
    location = db.Column(db.String(100))
    visit_time = db.Column(db.DateTime, default=datetime.utcnow)
    visit_count = db.Column(db.Integer, default=1)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_location(ip):
    try:
        with geoip2.database.Reader('GeoLite2-City.mmdb') as reader:
            response = reader.city(ip)
            return f"{response.city.name}, {response.country.name}"
    except:
        return "Bilinmiyor"

@app.before_request
def track_visitor():
    # Admin paneli isteklerini takip etme
    if request.path.startswith('/admin-panel'):
        return
    
    # Sağlık kontrolü isteklerini takip etme
    if request.path == '/healthz':
        return

    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    
    ua_string = request.user_agent.string
    user_agent = user_agents.parse(ua_string)
    
    visitor = Visitor.query.filter_by(ip_address=ip).first()
    
    if visitor:
        visitor.visit_count += 1
        visitor.visit_time = datetime.utcnow()
    else:
        location = get_location(ip)
        visitor = Visitor(
            ip_address=ip,
            user_agent=ua_string,
            device_type=user_agent.device.family,
            browser=user_agent.browser.family,
            location=location
        )
        db.session.add(visitor)
    
    try:
        db.session.commit()
    except:
        db.session.rollback()

@app.route('/admin-panel/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == app.config['ADMIN_USERNAME'] and password == app.config['ADMIN_PASSWORD']:
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username, password=password)
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for('admin'))
        
        flash('Geçersiz kullanıcı adı veya şifre')
    return render_template('login.html')

@app.route('/admin-panel')
@login_required
def admin():
    visitors = Visitor.query.order_by(Visitor.visit_time.desc()).all()
    return render_template('admin.html', visitors=visitors)

@app.route('/admin-panel/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/healthz')
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 