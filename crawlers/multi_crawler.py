# crawlers/multi_crawler.py - ADD AT THE VERY TOP
import os
import sys

# Change to project root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)  # Go up one level to FinalProject
os.chdir(project_root)  # Change working directory

print(f"📁 Changed to project root: {project_root}")
print(f"📁 Data will be saved to: {os.path.join(project_root, 'data')}")

import time
import pandas as pd
from datetime import datetime
import os
from typing import Dict, List
import sys

# Import platform-specific crawlers
try:
    from .amazon_crawler import AmazonCrawler
    from .jd_crawler import JDCrawler

    print("✅ Loaded platform crawlers")
except ImportError:
    sys.path.append('.')
    from crawlers.amazon_crawler import AmazonCrawler
    from crawlers.jd_crawler import JDCrawler


class MultiWebsiteCrawler:
    """MAIN CRAWLER MODULE - Handles multiple e-commerce websites"""

    SUPPORTED_PLATFORMS = {
        'amazon': {
            'name': 'Amazon',
            'class': AmazonCrawler,
            'default_proxy': False,
            'default_captcha': False
        },
        'jd': {
            'name': 'JD.com',
            'class': JDCrawler,
            'default_proxy': False,  # Changed from True to avoid proxy issues
            'default_captcha': True
        }
    }

    def __init__(self):
        self.results = {}
        self.crawlers = {}
        self.config = {}
        print("=" * 60)
        print("🛒 MULTI-WEBSITE CRAWLER MODULE INITIALIZED")
        print("=" * 60)

    def configure(self):
        """Configure the multi-crawler system"""
        print("\n⚙️ CONFIGURATION")
        print("-" * 40)

        # Keyword
        self.config['keyword'] = input("Search keyword: ").strip()
        if not self.config['keyword']:
            self.config['keyword'] = "laptop"

        # Pages (must be at least 10 per requirements)
        while True:
            pages_input = input("Pages per website (10-15): ").strip()
            if pages_input.isdigit() and 10 <= int(pages_input) <= 15:
                self.config['pages'] = int(pages_input)
                break
            print("❌ Must be 10-15 pages (project requirement)")

        # Platform selection
        print("\n🌐 SELECT PLATFORMS TO CRAWL:")
        for i, (key, info) in enumerate(self.SUPPORTED_PLATFORMS.items(), 1):
            print(f"  {i}. {info['name']}")

        selection = input("\nEnter numbers (e.g., '1 2' for both, or 'all'): ").strip().lower()

        if selection == 'all':
            self.config['platforms'] = list(self.SUPPORTED_PLATFORMS.keys())
        else:
            selected = []
            for num in selection.split():
                if num.isdigit() and 1 <= int(num) <= len(self.SUPPORTED_PLATFORMS):
                    key = list(self.SUPPORTED_PLATFORMS.keys())[int(num) - 1]
                    selected.append(key)
            self.config['platforms'] = selected or ['amazon', 'jd']

        # Anti-bot settings per platform
        print("\n🛡️ ANTI-BOT SETTINGS")
        for platform in self.config['platforms']:
            info = self.SUPPORTED_PLATFORMS[platform]
            print(f"\n  {info['name']}:")

            proxy_default = 'y' if info['default_proxy'] else 'n'
            proxy = input(f"    Use proxy? (y/n, default {proxy_default}): ").strip().lower()
            if not proxy:
                proxy = proxy_default

            captcha_default = 'y' if info['default_captcha'] else 'n'
            captcha = input(f"    Enable CAPTCHA handling? (y/n, default {captcha_default}): ").strip().lower()
            if not captcha:
                captcha = captcha_default

            self.config[f'{platform}_proxy'] = proxy == 'y'
            self.config[f'{platform}_captcha'] = captcha == 'y'

        return self.config

    def create_crawlers(self):
        """Create crawler instances for selected platforms"""
        print("\n" + "=" * 60)
        print("🚀 INITIALIZING CRAWLERS")
        print("=" * 60)

        for platform in self.config['platforms']:
            info = self.SUPPORTED_PLATFORMS[platform]
            crawler_class = info['class']

            print(f"\n🔧 Creating {info['name']} crawler...")

            use_proxy = self.config.get(f'{platform}_proxy', info['default_proxy'])
            use_captcha = self.config.get(f'{platform}_captcha', info['default_captcha'])

            self.crawlers[platform] = crawler_class(
                use_proxy=use_proxy,
                use_captcha=use_captcha
            )

            print(f"   ✓ Proxy: {'Enabled' if use_proxy else 'Disabled'}")
            print(f"   ✓ CAPTCHA: {'Enabled' if use_captcha else 'Disabled'}")

        return self.crawlers

    def crawl_all(self):
        """Execute crawling on all selected platforms"""
        print("\n" + "=" * 60)
        print("🌐 STARTING MULTI-PLATFORM CRAWLING")
        print("=" * 60)

        total_start = time.time()
        self.results = {}

        for i, (platform, crawler) in enumerate(self.crawlers.items(), 1):
            info = self.SUPPORTED_PLATFORMS[platform]

            print(f"\n{i}. {info['name'].upper()}")
            print("-" * 40)

            platform_start = time.time()

            # Execute the crawl
            products = crawler.search_products(
                keyword=self.config['keyword'],
                pages=self.config['pages']
            )

            platform_time = time.time() - platform_start

            self.results[platform] = {
                'products': products,
                'count': len(products),
                'time': platform_time
            }

            print(f"   ⏱️ Time: {platform_time:.1f}s")
            print(f"   📦 Products: {len(products)}")

            # IMPORTANT: Save platform results IMMEDIATELY
            self.save_platform_results(platform, products)

        total_time = time.time() - total_start
        print(f"\n✅ ALL CRAWLING COMPLETE")
        print(f"   Total time: {total_time:.1f}s")

        return self.results

    def save_platform_results(self, platform: str, products: List[Dict]):
        """Save/append results to platform-specific file"""
        if not products:
            print(f"   ⚠️ No products found for {platform}")
            return

        import pandas as pd
        import os

        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)

        # Create DataFrame
        df = pd.DataFrame(products)

        # Add metadata
        if 'platform' not in df.columns:
            df['platform'] = platform
        df['crawl_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df['search_keyword'] = self.config['keyword']

        # Platform-specific file
        platform_file = f"data/{platform}_products.csv"

        print(f"   💾 Processing {platform_file}...")
        print(f"   New products: {len(df)}")

        # ✅ APPEND to platform file
        if os.path.exists(platform_file):
            try:
                # Read existing data
                existing_df = pd.read_csv(platform_file)
                print(f"   Existing products: {len(existing_df)}")

                # Combine old and new data
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                print(f"   After combining: {len(combined_df)} products")

                # Remove duplicates
                if 'product_id' in combined_df.columns:
                    before = len(combined_df)
                    combined_df = combined_df.drop_duplicates(subset=['product_id'], keep='last')
                    after = len(combined_df)
                    if before != after:
                        print(f"   Removed {before - after} duplicates")

                # Save combined data
                combined_df.to_csv(platform_file, index=False, encoding='utf-8')
                print(f"   ✅ Appended. Total: {len(combined_df)} products")

            except Exception as e:
                print(f"   ❌ Error appending: {e}")
                # Save just the new data as fallback
                df.to_csv(platform_file, index=False, encoding='utf-8')
        else:
            # Create new file
            df.to_csv(platform_file, index=False, encoding='utf-8')
            print(f"   ✅ Created new file with {len(df)} products")

    def save_combined_results(self):
        """Save/append combined results to all_products.csv"""
        print("\n" + "=" * 60)
        print("💾 SAVING COMBINED RESULTS")
        print("=" * 60)

        all_new_products = []
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for platform, data in self.results.items():
            for product in data['products']:
                # Ensure platform is included
                product['platform'] = platform
                product['crawl_timestamp'] = current_time
                product['search_keyword'] = self.config['keyword']
                product['pages_crawled'] = self.config['pages']
                all_new_products.append(product)

        if not all_new_products:
            print("❌ No products to save")
            return None

        df = pd.DataFrame(all_new_products)
        all_file = 'data/all_products.csv'

        print(f"\n📊 Total new products from this crawl: {len(df)}")

        try:
            if os.path.exists(all_file):
                # Read existing data
                existing_df = pd.read_csv(all_file)
                print(f"📁 Existing all_products.csv: {len(existing_df)} products")

                # Combine old and new
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                print(f"📊 After combining: {len(combined_df)} products")

                # Remove duplicates
                if 'product_id' in combined_df.columns and 'platform' in combined_df.columns:
                    before = len(combined_df)
                    combined_df = combined_df.drop_duplicates(subset=['product_id', 'platform'], keep='last')
                    removed = before - len(combined_df)
                    if removed > 0:
                        print(f"🔄 Removed {removed} duplicate product_id+platform combinations")
                elif 'name' in combined_df.columns and 'platform' in combined_df.columns:
                    before = len(combined_df)
                    combined_df = combined_df.drop_duplicates(subset=['name', 'platform'], keep='last')
                    removed = before - len(combined_df)
                    if removed > 0:
                        print(f"🔄 Removed {removed} duplicate name+platform combinations")

                # Save combined data
                combined_df.to_csv(all_file, index=False, encoding='utf-8-sig')
                print(f"✅ Updated all_products.csv - Total: {len(combined_df)} products")

            else:
                # Create new file
                df.to_csv(all_file, index=False, encoding='utf-8-sig')
                print(f"✅ Created new all_products.csv with {len(df)} products")

        except Exception as e:
            print(f"❌ Error saving all_products.csv: {str(e)[:100]}")
            # Save just the new data
            df.to_csv(all_file, index=False, encoding='utf-8-sig')
            print(f"💾 Saved new data only ({len(df)} products)")

        # Show file status
        print("\n📁 FILE STATUS AFTER SAVE:")
        for file in ['amazon_products.csv', 'jd_products.csv', 'all_products.csv']:
            filepath = f"data/{file}"
            if os.path.exists(filepath):
                try:
                    file_df = pd.read_csv(filepath)
                    print(f"   {file}: {len(file_df)} products")
                except:
                    print(f"   {file}: Exists (error reading)")
            else:
                print(f"   {file}: Not created")

        return df

    def show_sample_data(self):
        """Display sample of collected data"""
        if not self.results:
            print("❌ No data to display")
            return

        print("\n" + "=" * 60)
        print("📋 SAMPLE DATA")
        print("=" * 60)

        for platform, data in self.results.items():
            if data['products']:
                info = self.SUPPORTED_PLATFORMS[platform]
                print(f"\n{info['name']} (showing 2 products):")
                print("-" * 40)

                df_sample = pd.DataFrame(data['products'][:2])
                display_cols = ['name', 'current_price', 'rating', 'store_name', 'crawl_timestamp']
                available_cols = [c for c in display_cols if c in df_sample.columns]

                if available_cols:
                    print(df_sample[available_cols].to_string(index=False))

    def run(self):
        """Main method to run the entire multi-crawler system"""
        print("\n" + "=" * 60)
        print("🎯 MULTI-WEBSITE CRAWLER SYSTEM")
        print("=" * 60)

        # Step 1: Configure
        self.configure()

        # Step 2: Create crawlers
        self.create_crawlers()

        # Step 3: Execute crawling
        self.crawl_all()

        # Step 4: Save combined results
        self.save_combined_results()

        # Step 5: Show sample
        self.show_sample_data()

        print("\n" + "=" * 60)
        print("✅ MULTI-WEBSITE CRAWLING COMPLETE")
        print("=" * 60)

        return self.results


def main():
    """Entry point for the Multi-website Crawler Module"""
    print("=" * 60)
    print("🛒 MULTI-WEBSITE CRAWLER MODULE")
    print("=" * 60)

    # Create and run the multi-crawler
    multicrawler = MultiWebsiteCrawler()
    results = multicrawler.run()

    if results:
        total_products = sum(data['count'] for data in results.values())
        print(f"\n🎉 FINAL SUMMARY:")
        print(f"   Total products collected: {total_products}")
        print(f"   Platforms crawled: {len(results)}")

        # Verify files were created/appended
        print("\n📁 FINAL FILE STATUS:")
        for file in ['amazon_products.csv', 'jd_products.csv', 'all_products.csv']:
            filepath = f"data/{file}"
            if os.path.exists(filepath):
                try:
                    file_size = os.path.getsize(filepath) / 1024  # KB
                    df = pd.read_csv(filepath)
                    print(f"   {file}: {len(df)} products ({file_size:.1f} KB)")
                except Exception as e:
                    print(f"   {file}: Exists but error reading ({str(e)[:50]})")
            else:
                print(f"   {file}: ❌ NOT CREATED - Check crawler output above")
    else:
        print("\n❌ No data collected.")


if __name__ == "__main__":
    main()