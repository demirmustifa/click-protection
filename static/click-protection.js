class ClickProtection {
    constructor(serverUrl = 'http://localhost:5000') {
        this.serverUrl = serverUrl;
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Tüm reklamları izle
        document.addEventListener('DOMContentLoaded', () => {
            this.watchAds();
        });

        // Dinamik olarak eklenen reklamlar için MutationObserver kullan
        const observer = new MutationObserver(() => {
            this.watchAds();
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    watchAds() {
        // Google Ads elementlerini bul
        const adElements = document.querySelectorAll('[data-ad-client], [data-ad-slot], .adsbygoogle');
        
        adElements.forEach(ad => {
            if (!ad.dataset.protected) {
                ad.dataset.protected = 'true';
                ad.addEventListener('click', (e) => this.handleAdClick(e));
            }
        });
    }

    async handleAdClick(event) {
        const clickInfo = {
            ip: await this.getIP(),
            user_agent: navigator.userAgent,
            referrer: document.referrer,
            campaign_id: this.getCampaignId(event.target),
            timestamp: new Date().toISOString()
        };

        try {
            const response = await fetch(`${this.serverUrl}/record-click`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(clickInfo)
            });

            const result = await response.json();

            if (result.is_fraudulent) {
                event.preventDefault();
                event.stopPropagation();
                console.warn('Şüpheli tıklama tespit edildi:', result.reason);
                return false;
            }
        } catch (error) {
            console.error('Tıklama kontrolü hatası:', error);
        }
    }

    async getIP() {
        try {
            const response = await fetch('https://api.ipify.org?format=json');
            const data = await response.json();
            return data.ip;
        } catch (error) {
            console.error('IP adresi alınamadı:', error);
            return '';
        }
    }

    getCampaignId(element) {
        // Google Ads kampanya ID'sini bulmaya çalış
        const adClient = element.closest('[data-ad-client]')?.dataset.adClient;
        const adSlot = element.closest('[data-ad-slot]')?.dataset.adSlot;
        return `${adClient || ''}-${adSlot || ''}`;
    }
}

// Global instance oluştur
window.clickProtection = new ClickProtection('https://servisimonline.com/click-protection'); 