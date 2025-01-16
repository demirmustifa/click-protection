import os

class Config:
    # MySQL veritabanı bağlantı bilgileri
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://u631245334_ip:100608011.Mustafa@localhost/u631245334_ip'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask uygulama ayarları
    SECRET_KEY = '100608011.Mustafa'  # Session güvenliği için
    
    # Uygulama ayarları
    ADMIN_USERNAME = '2599'
    ADMIN_PASSWORD = '100608011.Mustafa' 