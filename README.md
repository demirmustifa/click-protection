# Tıklama Dolandırıcılığı Koruma Sistemi

Bu proje, reklam kampanyalarınızı tıklama dolandırıcılığından korumak için geliştirilmiş bir sistemdir.

## Özellikler

- 24/7 Tıklama İzleme
- Otomatik Bot Tespiti
- IP Tabanlı Analiz
- Şüpheli Aktivite Raporlama
- API Entegrasyonu

## Kurulum

1. Gerekli bağımlılıkları yükleyin:
```bash
pip install -r requirements.txt
```

2. Uygulamayı başlatın:
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
    "referrer": "https://example.com",
    "campaign_id": "campaign_123"
}
```

### İstatistikler
```bash
GET /stats
```

## Güvenlik Özellikleri

- Bot Tespiti
- IP Reputation Kontrolü
- Anormal Davranış Analizi
- Gerçek Zamanlı İzleme 