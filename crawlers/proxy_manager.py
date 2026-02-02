import requests
import time

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.last_fetch = 0

    def fetch_free_proxies(self):
        #Fetch free proxies from public APIs
        sources = [
            'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
            'https://www.proxy-list.download/api/v1/get?type=http',
            'https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt'
        ]

        all_proxies = []
        for url in sources:
            try:
                response = requests.get(url, timeout=10)
                proxies = response.text.strip().split('\n')
                all_proxies.extend([p.strip() for p in proxies if p.strip()])
                print(f"📡 Fetched {len(proxies)} proxies from {url}")
            except:
                continue

        self.proxies = list(set(all_proxies))  # Remove duplicates
        self.last_fetch = time.time()
        return self.proxies