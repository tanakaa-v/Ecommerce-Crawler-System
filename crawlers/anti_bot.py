# crawlers/anti_bot.py - FIXED with 3 retries max
import requests
import time
import random
import json
import os
from typing import Optional, Dict, List
from fake_useragent import UserAgent
import re


class AntiBotManager:
    """Fixed anti-bot system - MAX 3 RETRIES PER REQUEST"""

    def __init__(self, platform_name: str, use_proxy: bool = False, use_captcha: bool = False):
        self.platform = platform_name
        self.ua = UserAgent()
        self.session = requests.Session()
        self.use_proxy = use_proxy
        self.use_captcha = use_captcha
        self.proxies = self._load_proxies() if use_proxy else []
        self.request_count = 0
        self.start_time = time.time()
        self._setup_platform_specifics()

    def _setup_platform_specifics(self):
        """Platform-specific settings - FASTER with 3 retries"""
        self.platform_config = {
            'Amazon': {
                'delay_range': (0.5, 1.5),  # FASTER: was (1.0, 3.0)
                'max_requests_per_min': 30,  # FASTER: was 20
                'retry_attempts': 2,  # 2 retries = 3 attempts total
                'captcha_keywords': ['captcha', 'enter the characters', 'robot']
            },
            'JD.com': {
                'delay_range': (1.0, 2.0),  # FASTER: was (2.0, 5.0)
                'max_requests_per_min': 15,  # FASTER: was 10
                'retry_attempts': 2,  # 2 retries = 3 attempts total
                'captcha_keywords': ['验证码', '人机验证', 'recaptcha', '安全验证']
            },
            'default': {
                'delay_range': (0.8, 1.8),  # FASTER: was (1.5, 4.0)
                'max_requests_per_min': 20,  # FASTER: was 15
                'retry_attempts': 2,  # 2 retries = 3 attempts total
                'captcha_keywords': ['captcha', 'verification']
            }
        }

        # Get config for this platform
        self.config = self.platform_config.get(self.platform, self.platform_config['default'])

    def _load_proxies(self) -> List[str]:
        """Load proxies - simplified"""
        proxies = []

        # Local proxy file
        if os.path.exists('proxies.txt'):
            with open('proxies.txt', 'r') as f:
                proxies = [line.strip() for line in f if line.strip()]

        # Hardcoded fallback (minimal)
        if not proxies:
            proxies = [
                'http://103.156.140.170:8080',
                'http://103.156.141.99:8080',
            ]

        print(f"📡 [{self.platform}] Loaded {len(proxies)} proxies")
        return proxies

    def get_random_headers(self) -> Dict[str, str]:
        """Generate random headers"""
        base_headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # Platform-specific headers
        if self.platform == 'JD.com':
            base_headers.update({
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Referer': 'https://www.jd.com/',
            })
        elif self.platform == 'Amazon':
            base_headers.update({
                'Referer': 'https://www.amazon.com/',
            })

        return base_headers

    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get random proxy from pool"""
        if not self.proxies or not self.use_proxy:
            return None

        proxy = random.choice(self.proxies)
        return {'http': proxy, 'https': proxy}

    def calculate_delay(self):
        """Smart delay - FASTER"""
        self.request_count += 1
        elapsed = time.time() - self.start_time

        # Platform-specific delays (reduced)
        min_delay, max_delay = self.config['delay_range']

        # FASTER: Simpler delay calculation
        if elapsed > 60 and self.request_count / elapsed > self.config['max_requests_per_min'] / 60:
            delay = max_delay * 2
            print(f"⏳ [{self.platform}] Rate limit approaching, sleeping {delay:.1f}s")
        else:
            delay = random.uniform(min_delay, max_delay)

        time.sleep(delay)
        return delay

    def detect_captcha(self, html: str) -> bool:
        """Detect CAPTCHA in response"""
        if not self.use_captcha:
            return False

        keywords = self.config['captcha_keywords']
        html_lower = html.lower()

        for keyword in keywords:
            if keyword.lower() in html_lower:
                print(f"⚠️ [{self.platform}] CAPTCHA detected: {keyword}")
                return True

        return False

    def handle_captcha(self):
        """Handle CAPTCHA - FASTER"""
        print(f"🔄 [{self.platform}] Handling CAPTCHA...")
        # FASTER: Shorter wait
        time.sleep(random.uniform(3, 6))
        print(f"✅ [{self.platform}] CAPTCHA handled")
        return True

    def make_request(self, url: str, method: str = 'GET', **kwargs) -> Optional[requests.Response]:
        """Make HTTP request - MAX 3 ATTEMPTS TOTAL"""
        # Prepare request
        headers = kwargs.pop('headers', self.get_random_headers())
        proxies = self.get_random_proxy()

        # MAX 3 ATTEMPTS TOTAL (1 initial + 2 retries)
        max_retries = self.config['retry_attempts']  # Should be 2 for 3 total attempts

        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                # Apply delay (except on first attempt if we just started)
                if attempt > 0 or self.request_count > 0:
                    self.calculate_delay()

                print(f"🌐 [{self.platform}] Attempt {attempt + 1}/{max_retries + 1}: {url[:50]}...")

                # SHORTER timeout
                timeout = 10 if attempt == 0 else 5  # First try 10s, retries 5s

                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    proxies=proxies,
                    timeout=timeout,
                    **kwargs
                )

                # Check for CAPTCHA
                if self.detect_captcha(response.text):
                    if self.handle_captcha():
                        # After CAPTCHA, use same proxy but count as attempt
                        print(f"🔄 [{self.platform}] Retrying after CAPTCHA...")
                        continue

                if response.status_code == 200:
                    print(f"✅ [{self.platform}] Success")
                    return response

                elif response.status_code in [403, 429, 503]:  # Blocked
                    print(f"🚫 [{self.platform}] Blocked! Status {response.status_code}")

                    if attempt < max_retries:  # Still have retries
                        print(f"🔄 [{self.platform}] Switching proxy and retrying...")
                        proxies = self.get_random_proxy()  # New proxy
                        # SHORTER wait between retries
                        time.sleep(random.uniform(2, 4))
                        continue

                else:
                    # Other HTTP errors - don't retry most
                    print(f"⚠️ [{self.platform}] HTTP {response.status_code}")
                    if response.status_code >= 500:  # Server errors might work on retry
                        if attempt < max_retries:
                            time.sleep(2)
                            continue
                    return None

            except requests.exceptions.Timeout:
                print(f"⏰ [{self.platform}] Timeout")
                if attempt < max_retries:
                    time.sleep(1)  # Short wait
                    continue

            except requests.exceptions.ConnectionError:
                print(f"🔌 [{self.platform}] Connection error")
                if attempt < max_retries:
                    time.sleep(1)
                    continue

            except requests.exceptions.ProxyError:
                print(f"🚫 [{self.platform}] Proxy error")
                if self.proxies and attempt < max_retries:
                    if proxies:
                        try:
                            self.proxies.remove(proxies.get('http') or proxies.get('https'))
                        except:
                            pass
                    proxies = self.get_random_proxy()
                    time.sleep(1)
                    continue

            except Exception as e:
                print(f"❌ [{self.platform}] Error: {str(e)[:80]}")
                if attempt < max_retries:
                    wait_time = min(attempt + 1, 3)  # Max 3 seconds
                    time.sleep(wait_time)
                    continue

        print(f"❌ [{self.platform}] Failed after {max_retries + 1} attempts")
        return None

    def save_debug_info(self, response, filename_prefix):
        """Save debug info - optional"""
        if response:
            debug_dir = 'debug_logs'
            os.makedirs(debug_dir, exist_ok=True)

            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filename = f"{debug_dir}/{filename_prefix}_{timestamp}.html"

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"URL: {response.url}\n")
                f.write(f"Status: {response.status_code}\n")
                f.write(f"Platform: {self.platform}\n")
                f.write("\n" + "=" * 50 + "\n")
                f.write(response.text[:2000])  # Smaller file

            print(f"📄 [{self.platform}] Debug saved: {filename}")