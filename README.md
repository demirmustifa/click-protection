# Click Protection Sistemi

Bu sistem, Google Ads reklamlarınızı bot saldırılarından ve sahte tıklamalardan korumak için geliştirilmiş bir koruma sistemidir.

## Sistem Nasıl Çalışır?

1. Google Ads reklamları click-protection.onrender.com üzerinden yönlendirilir
2. Her tıklama için şu kontroller yapılır:
   - IP bazlı limit kontrolü (24 saat içinde max 5 tıklama)
   - Hız kontrolü (1 dakika içinde max 2 tıklama)
   - Bot kontrolü (User-Agent analizi)
   - GCLID doğrulaması
3. Geçerli tıklamalar servisimonline.com'a yönlendirilir
4. Geçersiz tıklamalar engellenir

## Sistemin Artıları

1. **Bot Koruması**:
   - Bilinen bot türlerini otomatik engeller
   - Şüpheli IP'leri tespit eder
   - Hızlı/tekrarlı tıklamaları engeller

2. **Tıklama Limitleri**:
   - IP başına günlük limit (5 tıklama)
   - Dakika bazlı hız limiti (2 tıklama)
   - Kampanya bazlı takip

3. **İzleme ve Raporlama**:
   - Detaylı dashboard
   - Ülke bazlı istatistikler
   - IP bazlı tıklama kayıtları
   - Log sistemi

4. **Güvenlik**:
   - CORS koruması
   - Redis veya memory storage desteği
   - IP proxy tespiti

## Sistemin Eksikleri/Geliştirilebilecek Yönler

1. **Gelişmiş Bot Tespiti**:
   - JavaScript tabanlı bot tespiti eklenebilir
   - Fingerprint kontrolü eklenebilir
   - reCAPTCHA entegrasyonu yapılabilir

2. **Performans**:
   - CDN desteği eklenebilir
   - Önbellek sistemi geliştirilebilir
   - Yük dengeleme eklenebilir

3. **Raporlama**:
   - E-posta raporları eklenebilir
   - Daha detaylı analitik eklenebilir
   - PDF rapor çıktısı eklenebilir

4. **Güvenlik**:
   - SSL sertifikası zorunlu hale getirilebilir
   - IP whitelist/blacklist sistemi eklenebilir
   - DDoS koruması eklenebilir

## Kurulum

1. Google Ads reklamlarınızın hedef URL'lerini şu formatta güncelleyin:
```
https://click-protection.onrender.com/?gclid={gclid}&utm_source=google&utm_medium=cpc&utm_campaign=KAMPANYA_ADI
```

2. Sistem otomatik olarak çalışmaya başlayacaktır.

## Dashboard

Dashboard'a erişmek için:
```
https://click-protection.onrender.com/dashboard
```

## Öneriler

1. CloudFlare gibi bir CDN kullanılabilir
2. Düzenli yedekleme sistemi kurulabilir
3. IP veritabanı güncel tutulmalı
4. Loglar düzenli kontrol edilmeli

## Teknik Detaylar

- Python/Flask ile geliştirildi
- Redis veya memory storage kullanır
- Render.com üzerinde host ediliyor
- GeoIP veritabanı kullanıyor

## Destek

Sorun veya önerileriniz için iletişime geçebilirsiniz. 