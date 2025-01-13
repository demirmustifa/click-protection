import requests
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class IPChecker:
    def __init__(self):
        self.cache = {}
        # AbuseIPDB API anahtarınızı buraya ekleyin
        self.api_key = ""
    
    def check_ip(self, ip: str) -> Dict:
        if ip in self.cache:
            return self.cache[ip]
            
        try:
            # AbuseIPDB API'sini kullanarak IP kontrolü
            url = 'https://api.abuseipdb.com/api/v2/check'
            headers = {
                'Accept': 'application/json',
                'Key': self.api_key
            }
            params = {
                'ipAddress': ip,
                'maxAgeInDays': '30'
            }
            
            response = requests.get(url, headers=headers, params=params)
            result = response.json()
            
            is_suspicious = result.get('data', {}).get('abuseConfidenceScore', 0) > 25
            
            self.cache[ip] = {
                'is_suspicious': is_suspicious,
                'confidence_score': result.get('data', {}).get('abuseConfidenceScore', 0),
                'country': result.get('data', {}).get('countryCode', '')
            }
            
            return self.cache[ip]
            
        except Exception as e:
            logger.error(f"IP kontrol hatası: {str(e)}")
            return {'is_suspicious': False, 'error': str(e)} 