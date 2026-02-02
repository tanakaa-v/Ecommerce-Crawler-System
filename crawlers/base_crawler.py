from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import time
from anti_bot import AntiBotManager


class BaseCrawler(ABC):
    #Base class for all e-commerce crawlers

    def __init__(self, platform_name: str, use_proxy: bool = False, use_captcha: bool = False):
        self.platform = platform_name
        self.anti_bot = AntiBotManager(platform_name, use_proxy, use_captcha)
        self.products = []

    @abstractmethod
    def search_products(self, keyword: str, pages: int = 10) -> List[Dict]:
        #Search products
        pass

    @abstractmethod
    def parse_listing_page(self, html: str, page_num: int) -> List[Dict]:
        #Parse listing page
        pass

    @abstractmethod
    def parse_detail_page(self, product_url: str) -> Dict:
        #Parse detail page
        pass

    def make_request(self, url: str, **kwargs):
        #Make HTTP request using anti-bot system
        return self.anti_bot.make_request(url, **kwargs)

    def quick_request(self, url: str, max_attempts: int = 3):
        #Quick request, MAX 3 attempts
        for attempt in range(max_attempts):
            try:
                print(f"🚀 [{self.platform}] Quick attempt {attempt + 1}/{max_attempts}")
                response = self.anti_bot.make_request(url)
                if response and response.status_code == 200:
                    return response
                elif attempt < max_attempts - 1:
                    time.sleep(0.5)
            except:
                if attempt < max_attempts - 1:
                    time.sleep(0.5)
        return None

    def fast_search_page(self, keyword: str, page: int, max_time: int = 20):
        #Fast page search with timeout
        import threading

        result = []
        error = None

        def worker():
            nonlocal result, error
            try:
                page_products = self._scrape_single_page(keyword, page)
                result = page_products if page_products else []
            except Exception as e:
                error = e

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=max_time)

        if thread.is_alive():
            print(f"⏰ [{self.platform}] Page {page} timed out after {max_time}s")
            return []

        if error:
            print(f"❌ [{self.platform}] Page {page} error: {error}")
            return []

        return result

    def _scrape_single_page(self, keyword: str, page: int):
        """Internal method for single page scraping"""
        url = self._build_search_url(keyword, page)
        response = self.quick_request(url)

        if response and response.status_code == 200:
            return self.parse_listing_page(response.text, page)
        return None

    def _build_search_url(self, keyword: str, page: int) -> str:
        #Build search URL
        raise NotImplementedError("Child classes must implement _build_search_url")

    def save_to_csv(self, filename: str):
        #Save products to CSV
        import pandas as pd
        import os

        if not self.products:
            print(f"⚠️ No products to save for {self.platform}")
            return None

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        df = pd.DataFrame(self.products)
        df.to_csv(filename, index=False, encoding='utf-8')

        print(f"💾 {self.platform}: Saved {len(self.products)} products to {filename}")
        return df

    def show_sample(self, count: int = 3):
        #Show sample of collected products
        if not self.products:
            print(f"⚠️ No products to show for {self.platform}")
            return

        import pandas as pd

        df = pd.DataFrame(self.products[:count])
        print(f"\n📋 {self.platform} Sample (first {min(count, len(self.products))}):")
        print("-" * 60)

        # Select available columns to display
        display_cols = ['name', 'current_price', 'rating', 'store_name']
        available_cols = [c for c in display_cols if c in df.columns]

        if available_cols:
            print(df[available_cols].to_string(index=False))
        else:
            print("No displayable columns found")

        print("-" * 60)

    def get_stats(self) -> Dict:
        #Get crawling statistics
        return {
            'platform': self.platform,
            'product_count': len(self.products),
            'proxy_enabled': self.anti_bot.use_proxy,
            'captcha_enabled': self.anti_bot.use_captcha,
            'request_count': self.anti_bot.request_count
        }