# Proje Analiz Sonucu

## Genel Bakış
Bu proje, tıklama dolandırıcılığını tespit etmek ve önlemek için geliştirilmiş bir Flask web uygulamasıdır. Sistem, şüpheli tıklama aktivitelerini izleyerek reklam kampanyalarını korumayı amaçlamaktadır.

## Proje Yapısı
- `app.py`: Ana uygulama dosyası (162 satır)
- `gunicorn_config.py`: Gunicorn sunucu yapılandırması
- `requirements.txt`: Proje bağımlılıkları
- `static/`: Statik dosyalar dizini
- `templates/`: HTML şablonları dizini
- `click-protection/`: Koruma sistemi modülleri

## Temel Özellikler
1. **Tıklama İzleme Sistemi**
   - IP bazlı izleme
   - Oturum yönetimi
   - Hızlı çıkış tespiti
   - Bot aktivitesi kontrolü

2. **Güvenlik Mekanizmaları**
   - Otomatik bot tespiti
   - Şüpheli aktivite kaydı
   - Oturum bazlı analiz
   - Hızlı çıkış analizi

3. **API Endpoints**
   - `/record-click`: Tıklama kaydı
   - `/api/stats`: İstatistikler
   - `/api/quick-exit-report`: Hızlı çıkış raporu
   - `/api/suspicious-activities`: Şüpheli aktiviteler

## Teknoloji Yığını
- Flask 2.2.5
- Python 3.x
- Gunicorn 20.1.0
- Requests 2.26.0
- NumPy, Pandas ve Scikit-learn

## Önemli Özellikler
- 24/7 izleme sistemi
- Otomatik ping servisi
- Şüpheli aktivite raporlama
- IP tabanlı analiz
- Gerçek zamanlı izleme
- Dashboard arayüzü

## Geliştirme Notları
- Sistem modüler bir yapıda tasarlanmış
- Ölçeklenebilir mimari
- Detaylı loglama sistemi
- Güvenlik odaklı tasarım 