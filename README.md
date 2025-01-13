# Click Protection - Tıklama Dolandırıcılığı Koruma Sistemi

## Proje Hakkında
Click Protection, reklam kampanyalarınızı tıklama dolandırıcılığından korumak için geliştirilmiş kapsamlı bir koruma sistemidir. Sistem, şüpheli tıklama aktivitelerini gerçek zamanlı olarak tespit eder, analiz eder ve raporlar.

## Temel Özellikler

### 1. Tıklama Analizi ve Koruma
- IP tabanlı tıklama takibi
- Oturum bazlı analiz
- Hızlı çıkış tespiti
- Bot aktivitesi kontrolü
- Risk skoru hesaplama

### 2. Coğrafi Konum Analizi
- IP'den konum tespiti
- Dünya haritası üzerinde görselleştirme
- Ülke bazlı tıklama istatistikleri
- Risk bölgelerinin tespiti
- Şüpheli lokasyon analizi

### 3. Gerçek Zamanlı İzleme
- Anlık tıklama takibi
- Canlı dashboard görünümü
- 30 saniyede bir otomatik güncelleme
- Şüpheli aktivite uyarıları

### 4. Bildirim Sistemi
- E-posta bildirimleri
- Şüpheli aktivite uyarıları
- Bot tespiti bildirimleri
- Hızlı çıkış uyarıları

### 5. Raporlama
- Excel raporu indirme
- PDF raporu indirme
- Detaylı istatistikler
- Ülke bazlı raporlar

## Teknik Özellikler
- Flask web framework
- GeoIP2 konum veritabanı
- Leaflet.js harita görselleştirmesi
- Bootstrap 5 arayüz tasarımı
- Responsive dashboard

## Kurulum

1. Gereksinimleri yükleyin:
```bash
pip install -r requirements.txt
```

2. Environment değişkenlerini ayarlayın (.env dosyası):
```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
ADMIN_EMAIL=your-email@gmail.com
```

3. GeoLite2 veritabanını indirin ve projenin kök dizinine yerleştirin:
- GeoLite2-City.mmdb dosyasını MaxMind'dan indirin
- Projenin ana dizinine kopyalayın

4. Uygulamayı başlatın:
```bash
python app.py
```

## API Kullanımı

### Tıklama Kaydı
```bash
POST /record-click
Content-Type: application/json

{
    "ip": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "campaign_id": "campaign_123"
}
```

### İstatistikler
```bash
GET /api/stats
GET /api/location-stats
GET /api/quick-exit-report
GET /api/suspicious-activities
```

### Raporlar
```bash
GET /download-excel
GET /download-pdf
```

## Güvenlik Özellikleri
- IP reputation kontrolü
- Bot davranış analizi
- Hızlı çıkış tespiti
- Coğrafi konum risk analizi
- Şüpheli aktivite kaydı

## Kullanım Senaryoları
1. **Reklam Kampanyaları**: PPC kampanyalarınızı sahte tıklamalardan koruyun
2. **Web Siteleri**: Trafik kalitesini analiz edin
3. **E-ticaret**: Şüpheli kullanıcı davranışlarını tespit edin
4. **Analytics**: Gerçek trafik verilerinizi doğru analiz edin

## Planlanan Geliştirmeler
1. Gelişmiş bot tespiti
2. Makine öğrenmesi entegrasyonu
3. İki faktörlü kimlik doğrulama
4. Mobil uygulama desteği

## Lisans
Bu proje MIT lisansı altında lisanslanmıştır. 