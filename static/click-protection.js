class ClickProtection {
    constructor() {
        this.serverUrl = 'https://click-protection.onrender.com';
        this.setupEventListeners();
        console.log('Tıklama koruma sistemi aktif');
    }

    setupEventListeners() {
        // Mevcut reklamları dinle
        this.addClickListeners();

        // Yeni eklenen reklamları izle
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(() => {
                this.addClickListeners();
            });
        });

        // document.body varsa gözlemlemeye başla
        if (document.body) {
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        } else {
            // document.body hazır olduğunda gözlemlemeye başla
            document.addEventListener('DOMContentLoaded', () => {
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            });
        }
    }

    addClickListeners() {
        // Google Ads iframe'lerini bul
        const adIframes = document.querySelectorAll('iframe[id^="google_ads_iframe"]');
        adIframes.forEach(iframe => {
            if (!iframe.dataset.protected) {
                iframe.dataset.protected = 'true';
                iframe.addEventListener('click', (e) => this.handleClick(e));
            }
        });

        // Diğer reklam elementlerini bul
        const adElements = document.querySelectorAll('[class*="ad"], [id*="ad"], [class*="advertisement"]');
        adElements.forEach(element => {
            if (!element.dataset.protected) {
                element.dataset.protected = 'true';
                element.addEventListener('click', (e) => this.handleClick(e));
            }
        });
    }

    async handleClick(event) {
        const clickData = {
            url: window.location.href,
            timestamp: new Date().toISOString(),
            ip: await this.getIP(),
            user_agent: navigator.userAgent,
            referrer: document.referrer,
            target_element: event.target.tagName,
            campaign_id: this.getCampaignId(event.target)
        };

        try {
            const response = await fetch(`${this.serverUrl}/record-click`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(clickData)
            });

            const result = await response.json();
            if (!result.success) {
                console.warn('Şüpheli tıklama tespit edildi');
                event.preventDefault();
            }
        } catch (error) {
            console.error('Tıklama kaydedilirken hata oluştu:', error);
        }
    }

    async getIP() {
        try {
            const response = await fetch('https://api.ipify.org?format=json');
            const data = await response.json();
            return data.ip;
        } catch (error) {
            console.error('IP adresi alınamadı:', error);
            return 'unknown';
        }
    }

    getCampaignId(element) {
        // Google Ads için kampanya ID'sini bul
        const adContainer = element.closest('[id^="google_ads_iframe"]');
        if (adContainer) {
            const id = adContainer.id.match(/google_ads_iframe_(.+)$/);
            return id ? id[1] : 'unknown';
        }
        return 'unknown';
    }
}

// Sayfada sadece bir kez başlat
if (!window.clickProtection) {
    window.clickProtection = new ClickProtection();
} 