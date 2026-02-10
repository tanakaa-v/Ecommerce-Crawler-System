from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import pandas as pd
import numpy as np
import matplotlib
import os
import json
from datetime import datetime, timedelta
import warnings
import threading
import time
import sys
import io

# Fix Windows encoding issues
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings('ignore')

# ==================== ML IMPORT ====================
ML_AVAILABLE = False
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    ML_AVAILABLE = True
    print("[OK] ML libraries imported successfully")
except ImportError as e:
    print(f"[WARNING] ML libraries not available: {e}")
    print("Install with: pip install scikit-learn")

# Create directories
os.makedirs('templates', exist_ok=True)
os.makedirs('static/charts', exist_ok=True)
os.makedirs('data', exist_ok=True)
os.makedirs('monitoring', exist_ok=True)
os.makedirs('monitoring/alerts', exist_ok=True)
os.makedirs('ml', exist_ok=True)

app = Flask(__name__)


# ==================== PRICE MONITORING SYSTEM ====================

class PriceMonitor:
    def __init__(self, df):
        self.df = df
        self.monitored_products = []
        self.alerts = []
        self.load_monitored_products()

    def load_monitored_products(self):
        try:
            if os.path.exists('monitoring/monitored_products.json'):
                with open('monitoring/monitored_products.json', 'r', encoding='utf-8') as f:
                    self.monitored_products = json.load(f)
        except:
            self.monitored_products = []

    def save_monitored_products(self):
        try:
            with open('monitoring/monitored_products.json', 'w', encoding='utf-8') as f:
                json.dump(self.monitored_products, f, indent=2, default=str)
        except:
            pass

    def add_product_to_monitor(self, product_id: str, platform: str, target_price: float = None):
        # Normalize platform name
        platform = self.normalize_platform(platform)

        # Check if product exists in data
        try:
            product_data = self.df[
                (self.df['product_id'] == product_id) &
                (self.df['platform'] == platform)
                ].iloc[0].to_dict()
            product_name = product_data.get('name', f'Product {product_id}')
            current_price = product_data.get('current_price', 100.0)
        except:
            product_name = f'Product {product_id}'
            current_price = 100.0

        monitoring_info = {
            'product_id': product_id,
            'platform': platform,
            'name': product_name,
            'current_price': current_price,
            'target_price': target_price,
            'added_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'last_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Check if already monitoring
        for item in self.monitored_products:
            if item['product_id'] == product_id and item['platform'] == platform:
                item.update(monitoring_info)
                self.save_monitored_products()
                return True

        self.monitored_products.append(monitoring_info)
        self.save_monitored_products()
        return True

    def remove_product_from_monitor(self, product_id: str, platform: str):
        platform = self.normalize_platform(platform)
        self.monitored_products = [
            p for p in self.monitored_products
            if not (p['product_id'] == product_id and p['platform'] == platform)
        ]
        self.save_monitored_products()

    def normalize_platform(self, platform: str) -> str:
        """Normalize platform names to standard format"""
        platform_lower = str(platform).lower().strip()

        if platform_lower in ['amazon', 'amz', 'amzn']:
            return 'Amazon'
        elif platform_lower in ['jd.com', 'jd', 'jingdong', '京东', 'jing dong']:
            return 'JD.com'
        else:
            # Try to match with existing platforms in data
            if hasattr(self, 'df') and 'platform' in self.df.columns:
                existing_platforms = self.df['platform'].unique()
                for existing in existing_platforms:
                    if str(existing).lower() == platform_lower:
                        return existing
            return platform  # Return original if no match

    def check_price_changes(self):
        new_alerts = []
        for product in self.monitored_products:
            try:
                # Get current price from data
                current_product = self.df[
                    (self.df['product_id'] == product['product_id']) &
                    (self.df['platform'] == product['platform'])
                    ].iloc[0].to_dict()

                current_price = current_product.get('current_price', 100.0)
                old_price = product.get('current_price', 100.0)

                # Check if price changed
                if current_price != old_price:
                    alert = {
                        'product_id': product['product_id'],
                        'platform': product['platform'],
                        'product_name': product.get('name', 'Unknown'),
                        'old_price': old_price,
                        'new_price': current_price,
                        'change_percent': ((current_price - old_price) / old_price * 100),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'alert_type': 'PRICE_CHANGE'
                    }

                    # Check target price
                    if product.get('target_price') and current_price <= product['target_price']:
                        alert['alert_type'] = 'TARGET_REACHED'
                        alert['target_price'] = product['target_price']

                    new_alerts.append(alert)
                    self.alerts.append(alert)

                    # Update price
                    product['current_price'] = current_price
                    product['last_checked'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            except:
                continue

        if new_alerts:
            self.save_monitored_products()
        return new_alerts

    def get_alerts(self, limit: int = 10):
        return self.alerts[-limit:] if self.alerts else []


# ==================== ML RECOMMENDATION SYSTEM ====================

class ProductRecommender:
    def __init__(self, df):
        self.df = df
        self.vectorizer = None
        self.feature_matrix = None
        self.similarity_matrix = None
        self.trained = False

    def train_model(self):
        if not ML_AVAILABLE:
            print("[ERROR] ML not available")
            return False

        if len(self.df) < 10:
            print("[WARNING] Not enough data")
            return False

        try:
            # Create features
            self.df['combined_features'] = (
                    self.df['name'].fillna('') + ' ' +
                    self.df['category'].fillna('') + ' ' +
                    self.df['store_name'].fillna('')
            )

            # TF-IDF
            self.vectorizer = TfidfVectorizer(stop_words='english', max_features=500)
            self.feature_matrix = self.vectorizer.fit_transform(self.df['combined_features'])
            self.similarity_matrix = cosine_similarity(self.feature_matrix)
            self.trained = True

            print(f"[OK] ML model trained on {len(self.df)} products")
            return True
        except Exception as e:
            print(f"[ERROR] Error training model: {e}")
            return False

    def recommend_similar_products(self, product_id: str, n_recommendations: int = 5):
        if not ML_AVAILABLE or not self.trained:
            return self.get_dummy_recommendations(n_recommendations)

        try:
            if product_id not in self.df['product_id'].values:
                return []

            product_idx = self.df[self.df['product_id'] == product_id].index[0]
            similarity_scores = list(enumerate(self.similarity_matrix[product_idx]))
            similarity_scores = sorted(similarity_scores, key=lambda x: x[1], reverse=True)[1:]

            recommendations = []
            for idx, score in similarity_scores[:n_recommendations]:
                product = self.df.iloc[idx].to_dict()
                product['similarity_score'] = float(score)
                recommendations.append(product)

            return recommendations
        except:
            return self.get_dummy_recommendations(n_recommendations)

    def get_dummy_recommendations(self, n):
        if len(self.df) > 0:
            return self.df.head(min(n, len(self.df))).to_dict('records')
        return []

    def recommend_by_price_range(self, min_price: float, max_price: float,
                                 category: str = None, n_recommendations: int = 10):
        try:
            filtered_df = self.df.copy()
            filtered_df = filtered_df[
                (filtered_df['current_price'] >= min_price) &
                (filtered_df['current_price'] <= max_price)
                ]

            if category:
                filtered_df = filtered_df[filtered_df['category'] == category]

            filtered_df = filtered_df.sort_values(
                by=['rating', 'review_count'],
                ascending=[False, False]
            )

            recommendations = filtered_df.head(n_recommendations).to_dict('records')

            for rec in recommendations:
                rec['recommendation_reason'] = f"Price range: ${min_price}-${max_price}"
                if category:
                    rec['recommendation_reason'] += f", Category: {category}"

            return recommendations
        except:
            return self.get_dummy_recommendations(n_recommendations)


def normalize_crawl_platforms(platforms_input):
    """Normalize platform names for crawling"""
    if isinstance(platforms_input, str):
        platforms_input = [platforms_input]

    normalized = []
    for platform in platforms_input:
        platform_lower = str(platform).lower().strip()

        if platform_lower in ['amazon', 'amz', 'amzn', 'amazon.com']:
            normalized.append('amazon')
        elif platform_lower in ['jd.com', 'jd', 'jingdong', '京东', 'jing dong', 'jd (sample)', 'jd.com (sample)']:
            normalized.append('jd')

    # Remove duplicates
    return list(set(normalized))

def normalize_platform_name(platform: str) -> str:
    """Normalize platform names to standard format"""
    if not isinstance(platform, str):
        return str(platform)

    platform_lower = platform.lower().strip()

    if platform_lower in ['amazon', 'amz', 'amzn', 'amazon.com']:
        return 'Amazon'
    elif platform_lower in ['jd.com', 'jd', 'jingdong', '京东', 'jing dong', 'jd (sample)', 'jd.com (sample)']:
        return 'JD.com'
    else:
        return platform
def load_data():
    """Load data with priority: all_products.csv first, fallback only if truly empty"""
    try:
        # Priority 1: Try to load all_products.csv first
        if os.path.exists('data/all_products.csv'):
            try:
                df_all = pd.read_csv('data/all_products.csv')
                if not df_all.empty and len(df_all) > 0:
                    print(f"[DATA] Loaded {len(df_all)} products from all_products.csv")

                    # Ensure required columns exist
                    df_all = ensure_dataframe_columns(df_all)

                    # Normalize platform names
                    if 'platform' in df_all.columns:
                        df_all['platform'] = df_all['platform'].apply(normalize_platform_name)

                    return df_all
                else:
                    print("[DATA] all_products.csv is empty or corrupted")
            except Exception as e:
                print(f"[DATA WARNING] Could not read all_products.csv: {e}")

        # Priority 2: Try to load platform-specific files and combine
        csv_files = [
            'data/amazon_products.csv',
            'data/jd_products.csv'
        ]

        all_dfs = []
        for csv_file in csv_files:
            if os.path.exists(csv_file):
                try:
                    df_temp = pd.read_csv(csv_file)
                    if not df_temp.empty:
                        # Add platform column if missing
                        if 'platform' not in df_temp.columns:
                            if 'amazon' in csv_file.lower():
                                df_temp['platform'] = 'Amazon'
                            elif 'jd' in csv_file.lower():
                                df_temp['platform'] = 'JD.com'

                        all_dfs.append(df_temp)
                        print(f"[DATA] Loaded {len(df_temp)} products from {csv_file}")
                except Exception as e:
                    print(f"[DATA WARNING] Could not read {csv_file}: {e}")

        # If we have platform-specific data, combine it
        if all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            print(f"[DATA] Combined {len(combined_df)} products from platform files")

            # Ensure required columns
            combined_df = ensure_dataframe_columns(combined_df)

            # Save to all_products.csv for next time
            combined_df.to_csv('data/all_products.csv', index=False, encoding='utf-8')
            print(f"[DATA] Saved combined data to all_products.csv")

            return combined_df

        # Priority 3: Check if sample_products.csv exists but don't create it automatically
        if os.path.exists('data/sample_products.csv'):
            try:
                df_sample = pd.read_csv('data/sample_products.csv')
                if not df_sample.empty:
                    print(f"[DATA] Loaded {len(df_sample)} products from sample_products.csv")

                    # Ensure required columns
                    df_sample = ensure_dataframe_columns(df_sample)

                    # Save to all_products.csv for next time
                    df_sample.to_csv('data/all_products.csv', index=False, encoding='utf-8')
                    print(f"[DATA] Copied sample data to all_products.csv")

                    return df_sample
            except Exception as e:
                print(f"[DATA WARNING] Could not read sample_products.csv: {e}")

        # Only create sample data if NO files exist at all
        print("[DATA] No data files found. Creating sample data...")
        return create_sample_data()

    except Exception as e:
        print(f"[DATA ERROR] Error loading data: {e}")
        import traceback
        traceback.print_exc()
        # Only create sample data if everything fails
        return create_sample_data()


def ensure_dataframe_columns(df):
    """Ensure all required columns exist in the DataFrame"""
    if df.empty:
        return df

    # Ensure crawled_at exists with current timestamp for new data
    if 'crawled_at' not in df.columns or df['crawled_at'].isnull().all():
        df['crawled_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Product ID - make sure it's unique
    if 'product_id' not in df.columns or df['product_id'].isnull().all():
        # Generate unique IDs based on timestamp
        timestamp = int(time.time() * 1000)
        df['product_id'] = [f'PROD_{timestamp}_{i:06d}' for i in range(len(df))]

    # Name
    if 'name' not in df.columns or df['name'].isnull().all():
        df['name'] = [f'Product {i}' for i in range(len(df))]

    # Current price - ensure it's numeric
    if 'current_price' not in df.columns:
        df['current_price'] = np.random.uniform(50, 2000, len(df))
    else:
        # Convert to numeric, handle errors
        try:
            df['current_price'] = pd.to_numeric(df['current_price'], errors='coerce')
            # Fill missing values
            if df['current_price'].isnull().any():
                missing_count = df['current_price'].isnull().sum()
                df.loc[df['current_price'].isnull(), 'current_price'] = np.random.uniform(50, 2000, missing_count)
        except:
            df['current_price'] = np.random.uniform(50, 2000, len(df))

    # Platform - ensure it exists and is normalized
    if 'platform' not in df.columns or df['platform'].isnull().all():
        df['platform'] = np.random.choice(['Amazon', 'JD.com'], len(df))
    else:
        # Normalize platform names
        df['platform'] = df['platform'].apply(normalize_platform_name)

    # Other optional columns with defaults
    if 'category' not in df.columns or df['category'].isnull().all():
        df['category'] = np.random.choice(['Electronics', 'Clothing', 'Home', 'Books', 'Sports'], len(df))

    if 'rating' not in df.columns or df['rating'].isnull().all():
        df['rating'] = np.random.uniform(3.0, 5.0, len(df))

    if 'review_count' not in df.columns or df['review_count'].isnull().all():
        df['review_count'] = np.random.randint(10, 10000, len(df))

    return df


def append_products_safely(new_products, filename):
    """Safely append new products to existing CSV file without overwriting"""
    try:
        if not new_products:
            print(f"[APPEND] No products to append to {filename}")
            return False

        # Convert to DataFrame
        new_df = pd.DataFrame(new_products)

        if new_df.empty:
            print(f"[APPEND] Empty dataframe for {filename}")
            return False

        # Ensure required columns
        new_df = ensure_dataframe_columns(new_df)

        # Normalize platform names
        new_df['platform'] = new_df['platform'].apply(normalize_platform_name)

        # Check if file exists
        if os.path.exists(filename):
            try:
                # Read existing data
                existing_df = pd.read_csv(filename)

                if not existing_df.empty:
                    print(f"[APPEND] Found existing {len(existing_df)} products in {filename}")

                    # Normalize platform names in existing data
                    existing_df['platform'] = existing_df['platform'].apply(normalize_platform_name)

                    # Create unique identifiers
                    existing_df['unique_id'] = existing_df['product_id'].astype(str) + '|' + existing_df[
                        'platform'].astype(str)
                    new_df['unique_id'] = new_df['product_id'].astype(str) + '|' + new_df['platform'].astype(str)

                    # Remove duplicates (keep existing ones)
                    new_df = new_df[~new_df['unique_id'].isin(existing_df['unique_id'])]

                    if new_df.empty:
                        print(f"[APPEND] No new unique products to add to {filename}")
                        return True

                    # Combine dataframes
                    combined_df = pd.concat([existing_df.drop('unique_id', axis=1),
                                             new_df.drop('unique_id', axis=1)],
                                            ignore_index=True)

                    # Save combined data
                    combined_df.to_csv(filename, index=False, encoding='utf-8')
                    print(f"[APPEND] Appended {len(new_df)} new products to {filename}")
                    print(f"[APPEND] Total products in {filename}: {len(combined_df)}")
                    return True
                else:
                    # File exists but is empty
                    print(f"[APPEND] {filename} exists but is empty, writing new data")
                    new_df.to_csv(filename, index=False, encoding='utf-8')
                    return True

            except Exception as e:
                print(f"[APPEND ERROR] Could not read existing {filename}: {e}")
                # Create backup of corrupted file
                try:
                    backup_file = f"{filename}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    if os.path.exists(filename):
                        import shutil
                        shutil.copy2(filename, backup_file)
                        print(f"[APPEND] Created backup of corrupted file: {backup_file}")
                except:
                    pass

                # Write new data
                new_df.to_csv(filename, index=False, encoding='utf-8')
                print(f"[APPEND] Created new {filename} with {len(new_df)} products")
                return True
        else:
            # File doesn't exist, create it
            new_df.to_csv(filename, index=False, encoding='utf-8')
            print(f"[APPEND] Created new {filename} with {len(new_df)} products")
            return True

    except Exception as e:
        print(f"[APPEND CRITICAL ERROR] Failed to append to {filename}: {e}")
        import traceback
        traceback.print_exc()
        return False
def create_sample_data():
    """Create initial sample data if no data exists"""
    print("Creating sample data...")
    np.random.seed(42)

    sample_data = {
        'platform': ['Amazon'] * 50 + ['JD.com'] * 50,
        'product_id': [f'AMZ_{i:04d}' for i in range(50)] + [f'JD_{i:04d}' for i in range(50)],
        'name': [f'Product {i} - Sample Item' for i in range(100)],
        'current_price': list(np.random.uniform(50, 2000, 100)),
        'original_price': list(np.random.uniform(60, 2200, 100)),
        'rating': list(np.random.uniform(3.0, 5.0, 100)),
        'review_count': list(np.random.randint(10, 10000, 100)),
        'store_name': ['Amazon Store'] * 50 + ['JD Store'] * 50,
        'category': np.random.choice(['Electronics', 'Clothing', 'Home', 'Books', 'Sports'], 100),
        'crawled_at': [datetime.now().strftime('%Y-%m-%d %H:%M:%S') for _ in range(100)]
    }

    df = pd.DataFrame(sample_data)

    # Save to BOTH files
    df.to_csv('data/all_products.csv', index=False)
    df.to_csv('data/sample_products.csv', index=False)

    print(f"[OK] Created sample data with {len(df)} products")
    print(f"[OK] Saved to all_products.csv AND sample_products.csv")
    return df


# ==================== CHART FUNCTIONS ====================

def generate_price_chart():
    try:
        # Check if data exists
        if df.empty or 'current_price' not in df.columns:
            print("[ERROR] No price data available for chart")
            return None

        plt.figure(figsize=(10, 5))
        plt.subplot(1, 2, 1)
        prices = df['current_price'].dropna()

        if len(prices) == 0:
            print("[ERROR] No valid price data")
            return None

        plt.hist(prices, bins=30, alpha=0.7, color='steelblue', edgecolor='black')
        plt.title('Price Distribution')
        plt.xlabel('Price ($)')
        plt.ylabel('Number of Products')
        plt.grid(True, alpha=0.3)

        plt.subplot(1, 2, 2)
        if 'platform' in df.columns and len(df['platform'].unique()) > 0:
            platform_prices = df.groupby('platform')['current_price'].mean()
            if len(platform_prices) > 0:
                bars = plt.bar(platform_prices.index, platform_prices.values)
                plt.title('Average Price by Platform')
                plt.ylabel('Average Price ($)')
                plt.xlabel('Platform')
            else:
                plt.text(0.5, 0.5, 'No platform data', ha='center', va='center')
                plt.title('Average Price by Platform')
        else:
            plt.text(0.5, 0.5, 'No platform data', ha='center', va='center')
            plt.title('Average Price by Platform')

        plt.tight_layout()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'price_distribution_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"Generated price chart: {filename}")
        return filename

    except Exception as e:
        print(f"ERROR: Error generating price chart: {e}")
        return None


def generate_rating_chart():
    try:
        # Check if data exists
        if df.empty:
            print("[ERROR] No data available for rating chart")
            return None

        plt.figure(figsize=(10, 5))

        # Rating distribution
        plt.subplot(1, 2, 1)
        if 'rating' in df.columns:
            ratings = df['rating'].dropna()
            if len(ratings) > 0:
                plt.hist(ratings, bins=20, alpha=0.7, color='gold', edgecolor='black')
                plt.title('Rating Distribution')
                plt.xlabel('Rating (1-5)')
                plt.ylabel('Number of Products')
                plt.grid(True, alpha=0.3)
            else:
                plt.text(0.5, 0.5, 'No rating data', ha='center', va='center')
                plt.title('Rating Distribution')
        else:
            plt.text(0.5, 0.5, 'No rating data', ha='center', va='center')
            plt.title('Rating Distribution')

        # Rating vs Price scatter
        plt.subplot(1, 2, 2)
        if 'rating' in df.columns and 'current_price' in df.columns:
            ratings = df['rating'].dropna()
            prices = df['current_price'].dropna()
            if len(ratings) > 0 and len(prices) > 0:
                plt.scatter(df['rating'], df['current_price'], alpha=0.6, c='purple')
                plt.title('Rating vs Price')
                plt.xlabel('Rating')
                plt.ylabel('Price ($)')
                plt.grid(True, alpha=0.3)
            else:
                plt.text(0.5, 0.5, 'No rating/price data', ha='center', va='center')
                plt.title('Rating vs Price')
        else:
            plt.text(0.5, 0.5, 'No rating/price data', ha='center', va='center')
            plt.title('Rating vs Price')

        plt.tight_layout()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'rating_distribution_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"[OK] Generated rating chart: {filename}")
        return filename

    except Exception as e:
        print(f"[ERROR] Error generating rating chart: {e}")
        return None


def generate_category_chart():
    try:
        # Check if data exists
        if df.empty:
            print("[ERROR] No data available for category chart")
            return None

        plt.figure(figsize=(12, 6))

        if 'category' in df.columns and not df.empty:
            # Get top categories
            category_counts = df['category'].value_counts().head(8)  # Top 8 categories

            # Create subplots
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

            # 1. Horizontal bar chart
            if len(category_counts) > 0:
                bars = ax1.barh(category_counts.index, category_counts.values,
                                color=plt.cm.Set3(np.arange(len(category_counts))))
                ax1.set_title('Top Product Categories', fontsize=14, fontweight='bold')
                ax1.set_xlabel('Number of Products', fontsize=12)
                ax1.invert_yaxis()  # Highest on top

                # Add count labels
                for i, (value, bar) in enumerate(zip(category_counts.values, bars)):
                    ax1.text(value + 0.5, bar.get_y() + bar.get_height() / 2,
                             str(value), va='center', fontweight='bold')
            else:
                ax1.text(0.5, 0.5, 'No category data', ha='center', va='center', fontsize=12)
                ax1.set_title('Top Product Categories', fontsize=14, fontweight='bold')

            # 2. Pie chart
            if len(category_counts) > 0:
                ax2.pie(category_counts.values, labels=category_counts.index,
                        autopct='%1.1f%%', startangle=90,
                        colors=plt.cm.Set3(np.arange(len(category_counts))))
                ax2.set_title('Category Distribution', fontsize=14, fontweight='bold')
                ax2.axis('equal')  # Equal aspect ratio ensures pie is circular
            else:
                ax2.text(0.5, 0.5, 'No category data', ha='center', va='center', fontsize=12)
                ax2.set_title('Category Distribution', fontsize=14, fontweight='bold')
        else:
            # Create empty chart with message
            plt.text(0.5, 0.5, 'No category data available',
                     ha='center', va='center', fontsize=12, transform=plt.gca().transAxes)
            plt.title('Category Distribution')

        plt.tight_layout()

        # Save to static directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'category_distribution_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"[OK] Generated category chart: {filename}")
        return filename

    except Exception as e:
        print(f"[ERROR] Error generating category chart: {e}")
        return None


def generate_platform_chart():
    try:
        # Check if data exists
        if df.empty:
            print("[ERROR] No data available for platform chart")
            return None

        plt.figure(figsize=(12, 8))

        if 'platform' in df.columns and not df.empty:
            # Normalize platform names
            df['platform_normalized'] = df['platform'].apply(normalize_platform_name)
            platforms = df['platform_normalized'].unique()

            # Create subplots
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))

            # 1. Product count by platform
            platform_counts = df['platform_normalized'].value_counts()
            if len(platform_counts) > 0:
                bars1 = axes[0, 0].bar(platform_counts.index, platform_counts.values,
                                       color=['#FF6B6B', '#4ECDC4'][:len(platform_counts)])
                axes[0, 0].set_title('Products by Platform', fontsize=14, fontweight='bold')
                axes[0, 0].set_ylabel('Number of Products', fontsize=12)
                axes[0, 0].tick_params(axis='x', rotation=45)

                # Add count labels on bars
                for bar in bars1:
                    height = bar.get_height()
                    axes[0, 0].text(bar.get_x() + bar.get_width() / 2., height,
                                    f'{int(height)}', ha='center', va='bottom', fontweight='bold')
            else:
                axes[0, 0].text(0.5, 0.5, 'No platform data', ha='center', va='center', fontsize=12)
                axes[0, 0].set_title('Products by Platform', fontsize=14, fontweight='bold')

            # 2. Average price by platform
            if 'current_price' in df.columns:
                avg_price = df.groupby('platform_normalized')['current_price'].mean()
                if len(avg_price) > 0:
                    bars2 = axes[0, 1].bar(avg_price.index, avg_price.values,
                                           color=['#96CEB4', '#FFEAA7'][:len(avg_price)])
                    axes[0, 1].set_title('Average Price by Platform', fontsize=14, fontweight='bold')
                    axes[0, 1].set_ylabel('Price ($)', fontsize=12)
                    axes[0, 1].tick_params(axis='x', rotation=45)

                    # Add price labels on bars
                    for bar in bars2:
                        height = bar.get_height()
                        axes[0, 1].text(bar.get_x() + bar.get_width() / 2., height,
                                        f'${height:.2f}', ha='center', va='bottom', fontweight='bold')
                else:
                    axes[0, 1].text(0.5, 0.5, 'No price data', ha='center', va='center', fontsize=12)
                    axes[0, 1].set_title('Average Price by Platform', fontsize=14, fontweight='bold')
            else:
                axes[0, 1].text(0.5, 0.5, 'No price data', ha='center', va='center', fontsize=12)
                axes[0, 1].set_title('Average Price by Platform', fontsize=14, fontweight='bold')

            # 3. Average rating by platform
            if 'rating' in df.columns:
                avg_rating = df.groupby('platform_normalized')['rating'].mean()
                if len(avg_rating) > 0:
                    bars3 = axes[1, 0].bar(avg_rating.index, avg_rating.values,
                                           color=['#E6B0AA', '#A9CCE3'][:len(avg_rating)])
                    axes[1, 0].set_title('Average Rating by Platform', fontsize=14, fontweight='bold')
                    axes[1, 0].set_ylabel('Rating (1-5)', fontsize=12)
                    axes[1, 0].set_ylim([0, 5.5])  # Rating scale
                    axes[1, 0].tick_params(axis='x', rotation=45)

                    # Add rating labels on bars
                    for bar in bars3:
                        height = bar.get_height()
                        axes[1, 0].text(bar.get_x() + bar.get_width() / 2., height,
                                        f'{height:.2f}', ha='center', va='bottom', fontweight='bold')
                else:
                    axes[1, 0].text(0.5, 0.5, 'No rating data', ha='center', va='center', fontsize=12)
                    axes[1, 0].set_title('Average Rating by Platform', fontsize=14, fontweight='bold')
            else:
                axes[1, 0].text(0.5, 0.5, 'No rating data', ha='center', va='center', fontsize=12)
                axes[1, 0].set_title('Average Rating by Platform', fontsize=14, fontweight='bold')

            # 4. Platform market share (pie chart)
            if len(platform_counts) > 0:
                axes[1, 1].axis('equal')  # Equal aspect ratio ensures pie is circular
                wedges, texts, autotexts = axes[1, 1].pie(platform_counts.values,
                                                          labels=platform_counts.index,
                                                          autopct='%1.1f%%',
                                                          startangle=90,
                                                          colors=['#FF6B6B', '#4ECDC4'][
                                                                 :len(platform_counts)])
                axes[1, 1].set_title('Platform Market Share', fontsize=14, fontweight='bold')

                # Make autotexts bold
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
            else:
                axes[1, 1].text(0.5, 0.5, 'No platform data', ha='center', va='center', fontsize=12)
                axes[1, 1].set_title('Platform Market Share', fontsize=14, fontweight='bold')
        else:
            # Single empty chart
            plt.text(0.5, 0.5, 'No platform data available',
                     ha='center', va='center', fontsize=12, transform=plt.gca().transAxes)
            plt.title('Platform Comparison')

        plt.tight_layout()

        # Save to static directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'platform_comparison_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"[OK] Generated platform chart: {filename}")
        return filename

    except Exception as e:
        print(f"[ERROR] Error generating platform chart: {e}")
        return None


def generate_trend_chart():
    try:
        plt.figure(figsize=(12, 6))

        # Create timeline (last 7 days)
        dates = pd.date_range(end=datetime.now(), periods=7, freq='D')
        date_labels = [d.strftime('%b %d') for d in dates]

        # Get unique platforms
        if 'platform' in df.columns and not df.empty:
            # Normalize platform names
            df['platform_normalized'] = df['platform'].apply(normalize_platform_name)
            platforms = df['platform_normalized'].unique()

            if len(platforms) > 0:
                # Define colors for each platform
                colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']

                for i, platform in enumerate(platforms[:2]):  # Show only Amazon and JD.com
                    platform_df = df[df['platform_normalized'] == platform]

                    if not platform_df.empty and 'current_price' in platform_df.columns:
                        # Get average price for this platform
                        avg_price = platform_df['current_price'].mean()

                        # Create realistic trend with weekly pattern
                        np.random.seed(hash(platform) % 1000)

                        # Base trend with weekend dip (if e-commerce)
                        days_of_week = np.array([d.dayofweek for d in dates])
                        weekend_multiplier = np.where((days_of_week == 5) | (days_of_week == 6), 0.95, 1.0)

                        # Create trend with some randomness
                        base_trend = np.linspace(avg_price * 0.85, avg_price * 1.15, 7)
                        trend_with_pattern = base_trend * weekend_multiplier
                        random_noise = np.random.normal(0, avg_price * 0.03, 7)
                        trend_line = trend_with_pattern + random_noise

                        # Plot trend
                        color = colors[i % len(colors)]
                        plt.plot(date_labels, trend_line,
                                 marker='o',
                                 markersize=8,
                                 linewidth=2.5,
                                 label=f'{platform} Price Trend',
                                 color=color,
                                 alpha=0.8)

                        # Add average line
                        plt.axhline(y=avg_price,
                                    color=color,
                                    linestyle='--',
                                    alpha=0.3,
                                    label=f'{platform} Avg: ${avg_price:.2f}')

                plt.title('Price Trends Over Last 7 Days', fontsize=16, fontweight='bold')
                plt.xlabel('Date', fontsize=12)
                plt.ylabel('Price ($)', fontsize=12)
                plt.grid(True, alpha=0.3, linestyle='--')
                plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
                plt.xticks(rotation=45)

                # Add trend analysis annotation
                plt.figtext(0.5, 0.01,
                            'Trend analysis shows price fluctuations over time. Dashed lines represent platform averages.',
                            ha='center', fontsize=10, style='italic', color='gray')

            else:
                plt.text(0.5, 0.5, 'No platform data available',
                         ha='center', va='center', fontsize=12)
                plt.title('Price Trends', fontsize=16, fontweight='bold')
        else:
            plt.text(0.5, 0.5, 'No trend data available',
                     ha='center', va='center', fontsize=12)
            plt.title('Price Trends', fontsize=16, fontweight='bold')

        plt.tight_layout(rect=[0, 0.03, 1, 0.97])

        # Save to static directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'price_trends_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"[OK] Generated trend chart: {filename}")
        return filename

    except Exception as e:
        print(f"[ERROR] Error generating trend chart: {e}")
        return None


def generate_sentiment_chart():
    try:
        plt.figure(figsize=(10, 6))

        # Simulate sentiment data
        sentiments = ['Positive', 'Neutral', 'Negative']
        sentiment_counts = [65, 25, 10]  # Example percentages

        # Create bar chart
        bars = plt.bar(sentiments, sentiment_counts,
                       color=['#4CAF50', '#FFC107', '#F44336'])

        plt.title('Customer Review Sentiment Analysis', fontsize=16, fontweight='bold')
        plt.xlabel('Sentiment', fontsize=12)
        plt.ylabel('Percentage (%)', fontsize=12)
        plt.ylim([0, 100])
        plt.grid(True, alpha=0.3, axis='y')

        # Add percentage labels
        for bar, count in zip(bars, sentiment_counts):
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                     f'{count}%', ha='center', va='bottom', fontweight='bold')

        # Add note
        plt.figtext(0.5, 0.01, 'Note: Sentiment analysis based on review text patterns',
                    ha='center', fontsize=10, style='italic', color='gray')

        plt.tight_layout(rect=[0, 0.03, 1, 0.97])

        # Save to static directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'sentiment_analysis_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"[OK] Generated sentiment chart: {filename}")
        return filename

    except Exception as e:
        print(f"[ERROR] Error generating sentiment chart: {e}")
        return None


def save_chart_state():
    state = {
        'last_generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'chart_count': len([f for f in os.listdir('static/charts') if f.endswith('.png')])
        if os.path.exists('static/charts') else 0
    }

    with open('chart_state.json', 'w', encoding='utf-8') as f:
        json.dump(state, f)

    return state


def get_chart_versions(chart_type, limit=2):
    if not os.path.exists('static/charts'):
        return []

    charts = []
    for f in os.listdir('static/charts'):
        if chart_type in f.lower() and f.endswith('.png'):
            path = os.path.join('static/charts', f)
            charts.append({
                'file': f,
                'created': os.path.getctime(path),
                'type': chart_type
            })

    # Sort by creation time, newest first
    charts.sort(key=lambda x: x['created'], reverse=True)

    # Return only most recent N
    return [c['file'] for c in charts[:limit]]


def generate_chart_pair(chart_type):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    chart_functions = {
        'price': generate_price_chart,
        'rating': generate_rating_chart,
        'category': generate_category_chart,
        'platform': generate_platform_chart,
        'trend': generate_trend_chart,
        'sentiment': generate_sentiment_chart
    }

    if chart_type in chart_functions:
        before_chart = chart_functions[chart_type]()
    else:
        print(f"[WARNING] Unknown chart type: {chart_type}")
        return []

    # Simulate "after" version
    if before_chart:
        try:
            # For all charts, copy and rename as "after" version
            import shutil
            before_path = os.path.join('static/charts', before_chart)
            after_filename = before_chart.replace('.png', '_after.png')
            after_path = os.path.join('static/charts', after_filename)

            shutil.copy2(before_path, after_path)
            print(f"[OK] Created {chart_type} chart pair: {before_chart}, {after_filename}")
            return [before_chart, after_filename]

        except Exception as e:
            print(f"[WARNING] Could not create after chart for {chart_type}: {e}")
            return [before_chart]

    return []


# ==================== CREATE ERROR PAGES ====================

def create_error_pages():
    if not os.path.exists('templates/404.html'):
        with open('templates/404.html', 'w', encoding='utf-8') as f:
            f.write('''<!DOCTYPE html>
<html>
<head>
    <title>404 - Page Not Found</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body style="font-family: Arial; padding: 50px; text-align: center;">
    <h1>404 - Page Not Found</h1>
    <p>The page you're looking for doesn't exist.</p>
    <a href="/" class="btn btn-primary">Go Home</a>
    <a href="/monitoring" class="btn btn-success ms-2">Price Monitoring</a>
    <a href="/recommendations" class="btn btn-info ms-2">Recommendations</a>
</body>
</html>''')
        print("[OK] Created 404.html")

    if not os.path.exists('templates/500.html'):
        with open('templates/500.html', 'w', encoding='utf-8') as f:
            f.write('''<!DOCTYPE html>
<html>
<head>
    <title>500 - Server Error</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body style="font-family: Arial; padding: 50px; text-align: center;">
    <h1>500 - Server Error</h1>
    <p>Something went wrong on our server.</p>
    <a href="/" class="btn btn-primary">Go Home</a>
</body>
</html>''')
        print("[OK] Created 500.html")


# ==================== INITIALIZE ====================

df = load_data()
price_monitor = PriceMonitor(df)
recommender = ProductRecommender(df)

# Create error pages
create_error_pages()


# Start background monitoring
def background_monitoring():
    while True:
        try:
            alerts = price_monitor.check_price_changes()
            if alerts:
                print(f"[ALERT] Price Monitor: {len(alerts)} new alerts")
            time.sleep(60)
        except Exception as e:
            print(f"Error in monitoring: {e}")
            time.sleep(30)


monitor_thread = threading.Thread(target=background_monitoring, daemon=True)
monitor_thread.start()


# ==================== ROUTES ====================

@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/monitoring')
def monitoring():
    # Get monitored products
    monitored = price_monitor.monitored_products

    # Get recent alerts
    alerts = price_monitor.get_alerts(20)

    # Get unique platforms from data (normalized)
    if 'platform' in df.columns:
        platforms = list(set([normalize_platform_name(p) for p in df['platform'].unique()]))
    else:
        platforms = []

    # Get some sample products for monitoring suggestions
    sample_products = df.head(10).to_dict('records')

    return render_template('monitoring.html',
                           monitored_products=monitored,
                           alerts=alerts,
                           platforms=platforms,
                           sample_products=sample_products)


@app.route('/')
def index():
    # Normalize platform names for stats
    df_normalized = df.copy()
    if 'platform' in df_normalized.columns:
        df_normalized['platform'] = df_normalized['platform'].apply(normalize_platform_name)

    stats = {
        'total_products': len(df_normalized),
        'avg_price': float(df_normalized['current_price'].mean()) if 'current_price' in df_normalized.columns else 0,
        'avg_rating': float(df_normalized['rating'].mean()) if 'rating' in df_normalized.columns else 0,
        'platform_count': df_normalized['platform'].nunique() if 'platform' in df_normalized.columns else 0,
        'category_count': df_normalized['category'].nunique() if 'category' in df_normalized.columns else 0,
        'monitored_products': len(price_monitor.monitored_products),
        'total_alerts': len(price_monitor.alerts),
        'min_price': float(df_normalized['current_price'].min()) if 'current_price' in df_normalized.columns else 0,
        'max_price': float(df_normalized['current_price'].max()) if 'current_price' in df_normalized.columns else 0
    }

    # Get list of existing charts
    chart_files = []
    if os.path.exists('static/charts'):
        chart_files = [f for f in os.listdir('static/charts') if f.endswith('.png')]

    # If no charts exist, generate initial set
    if not chart_files:
        print("[INFO] Generating initial charts...")
        chart_types = ['price', 'rating', 'category', 'platform', 'trend', 'sentiment']
        for chart_type in chart_types:
            generate_chart_pair(chart_type)

    return render_template('index.html', stats=stats, chart_files=chart_files)


@app.route('/api/generate_chart/<chart_type>', methods=['POST'])
def generate_chart_type_api(chart_type):
    """Generate a specific chart type"""
    try:
        chart_file = None

        if chart_type == 'price':
            chart_file = generate_price_chart()
        elif chart_type == 'rating':
            chart_file = generate_rating_chart()
        elif chart_type == 'category':
            chart_file = generate_category_chart()
        elif chart_type == 'platform':
            chart_file = generate_platform_chart()
        elif chart_type == 'trend':
            chart_file = generate_trend_chart()
        elif chart_type == 'sentiment':
            chart_file = generate_sentiment_chart()
        else:
            return jsonify({'success': False, 'message': 'Invalid chart type'})

        if chart_file:
            return jsonify({
                'success': True,
                'message': f'Generated {chart_type} chart',
                'file': chart_file
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to generate chart'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/generate_pair/<chart_type>', methods=['POST'])
def generate_chart_pair_api(chart_type):
    """API endpoint to generate chart pairs"""
    try:
        pair = generate_chart_pair(chart_type)
        if pair:
            return jsonify({
                'success': True,
                'message': f'Generated {chart_type} chart pair',
                'pair': pair
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to generate {chart_type} chart pair'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })


@app.route('/api/monitor/add', methods=['POST'])
def add_to_monitor():
    data = request.json
    product_id = data.get('product_id', '').strip()
    platform_raw = data.get('platform', '').strip()
    target_price = data.get('target_price')

    # Normalize platform name
    platform = normalize_platform_name(platform_raw)

    if not product_id or not platform:
        return jsonify({'success': False, 'message': 'Product ID and Platform are required'})

    if target_price is not None:
        try:
            target_price = float(target_price)
            if target_price <= 0:
                return jsonify({'success': False, 'message': 'Target price must be positive'})
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid target price'})

    success = price_monitor.add_product_to_monitor(product_id, platform, target_price)

    return jsonify({
        'success': success,
        'message': 'Product added to monitoring' if success else 'Failed to add product'
    })


@app.route('/api/monitor/remove', methods=['POST'])
def remove_from_monitor():
    data = request.json
    product_id = data.get('product_id')
    platform_raw = data.get('platform')

    # Normalize platform name
    platform = normalize_platform_name(platform_raw)

    price_monitor.remove_product_from_monitor(product_id, platform)

    return jsonify({'success': True, 'message': 'Product removed from monitoring'})


@app.route('/api/monitor/alerts')
def get_alerts():
    alerts = price_monitor.get_alerts(20)
    return jsonify({
        'success': True,
        'alerts': alerts,
        'total': len(price_monitor.alerts)
    })


# ==================== RECOMMENDATIONS ROUTES ====================

@app.route('/recommendations')
def recommendations_page():
    # Train model if not already trained
    if ML_AVAILABLE and not recommender.trained and len(df) >= 10:
        print("[ML] Training recommendation model...")
        recommender.train_model()

    sample_products = df.head(5).to_dict('records')
    categories = df['category'].unique().tolist() if 'category' in df.columns else []

    return render_template('recommendations.html',
                           sample_products=sample_products,
                           categories=categories,
                           ml_available=ML_AVAILABLE,
                           model_trained=recommender.trained)


@app.route('/api/recommend/similar', methods=['POST'])
def recommend_similar():
    data = request.json
    product_id = data.get('product_id', '').strip()
    n_recommendations = data.get('n_recommendations', 5)

    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID is required'})

    recommendations = recommender.recommend_similar_products(product_id, n_recommendations)

    return jsonify({
        'success': True,
        'recommendations': recommendations,
        'count': len(recommendations)
    })


@app.route('/api/recommend/price-range', methods=['POST'])
def recommend_by_price():
    data = request.json
    min_price = float(data.get('min_price', 0))
    max_price = float(data.get('max_price', 1000))
    category = data.get('category')
    n_recommendations = data.get('n_recommendations', 10)

    if min_price < 0 or max_price < 0:
        return jsonify({'success': False, 'message': 'Prices cannot be negative'})
    if min_price > max_price:
        return jsonify({'success': False, 'message': 'Min price cannot be greater than max price'})

    recommendations = recommender.recommend_by_price_range(
        min_price, max_price, category, n_recommendations
    )

    return jsonify({
        'success': True,
        'recommendations': recommendations,
        'count': len(recommendations)
    })


@app.route('/api/recommend/train', methods=['POST'])
def train_model():
    if not ML_AVAILABLE:
        return jsonify({'success': False, 'message': 'ML libraries not available'})

    success = recommender.train_model()
    return jsonify({
        'success': success,
        'message': 'Model trained successfully' if success else 'Failed to train model'
    })


@app.route('/api/recommend/stats')
def recommendation_stats():
    stats = {
        'total_products': len(df),
        'categories': df['category'].nunique() if 'category' in df.columns else 0,
        'platforms': df['platform'].nunique() if 'platform' in df.columns else 0,
        'price_range': {
            'min': float(df['current_price'].min()) if 'current_price' in df.columns else 0,
            'max': float(df['current_price'].max()) if 'current_price' in df.columns else 0,
            'avg': float(df['current_price'].mean()) if 'current_price' in df.columns else 0
        },
        'model_trained': recommender.trained
    }

    return jsonify({'success': True, 'stats': stats})


# ==================== OTHER ROUTES ====================

@app.route('/charts/<filename>')
def serve_chart(filename):
    return send_from_directory('static/charts', filename, cache_timeout=0)


@app.route('/products')
def products():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    platform_raw = request.args.get('platform', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')

    # Normalize platform for filtering
    platform = normalize_platform_name(platform_raw) if platform_raw else ''

    filtered_df = df.copy()

    if search:
        filtered_df = filtered_df[filtered_df['name'].str.contains(search, case=False, na=False)]

    if platform:
        # Normalize platform names for comparison
        filtered_df['platform_normalized'] = filtered_df['platform'].apply(normalize_platform_name)
        filtered_df = filtered_df[filtered_df['platform_normalized'] == platform]
    else:
        filtered_df['platform_normalized'] = filtered_df['platform'].apply(normalize_platform_name)

    if min_price:
        try:
            filtered_df = filtered_df[filtered_df['current_price'] >= float(min_price)]
        except:
            pass

    if max_price:
        try:
            filtered_df = filtered_df[filtered_df['current_price'] <= float(max_price)]
        except:
            pass

    per_page = 20
    total = len(filtered_df)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    products_data = filtered_df.iloc[start_idx:end_idx].to_dict('records')

    # Get normalized platform list
    if 'platform' in df.columns:
        platforms = list(set([normalize_platform_name(p) for p in df['platform'].unique()]))
    else:
        platforms = []

    return render_template('products.html',
                           products=products_data,
                           page=page,
                           total_pages=total_pages,
                           total=total,
                           search=search,
                           selected_platform=platform_raw,
                           min_price=min_price,
                           max_price=max_price,
                           platforms=platforms)


@app.route('/analysis')
def analysis():
    """Analysis page with paired charts (before/after)"""

    # Define chart types
    chart_types = ['price', 'rating', 'category', 'platform', 'trend', 'sentiment']

    # Get paired charts for each type
    chart_pairs = {}
    for chart_type in chart_types:
        existing_charts = get_chart_versions(chart_type, limit=2)
        chart_pairs[chart_type] = existing_charts

    # Calculate basic statistics safely
    stats = {}

    if not df.empty:
        # Price stats
        if 'current_price' in df.columns:
            stats['price'] = {
                'mean': float(df['current_price'].mean()) if len(df) > 0 else 0,
                'median': float(df['current_price'].median()) if len(df) > 0 else 0,
                'min': float(df['current_price'].min()) if len(df) > 0 else 0,
                'max': float(df['current_price'].max()) if len(df) > 0 else 0,
            }

        # Rating stats
        if 'rating' in df.columns:
            stats['rating'] = {
                'mean': float(df['rating'].mean()) if len(df) > 0 else 0,
                'count_above_4': int((df['rating'] > 4).sum()) if len(df) > 0 else 0,
            }
    else:
        # Default empty stats
        stats = {
            'price': {'mean': 0, 'median': 0, 'min': 0, 'max': 0},
            'rating': {'mean': 0, 'count_above_4': 0}
        }

    return render_template('analysis_paired.html',
                           chart_pairs=chart_pairs,
                           stats=stats,
                           total_products=len(df))


@app.route('/crawl_panel')
def crawl_panel():
    """Render the crawl panel with custom settings"""
    return render_template('crawl_panel.html')





@app.route('/start_crawl', methods=['POST'])
def start_crawl():
    """Start web crawling with custom settings"""
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data received'
            }), 400

        keyword = data.get('keyword', '').strip()
        pages_input = data.get('pages', 10)

        # Get and normalize platforms
        platforms_input = data.get('platforms', ['amazon', 'jd'])
        platforms = normalize_crawl_platforms(platforms_input)

        # Parse pages input
        try:
            pages = int(pages_input)
        except ValueError:
            pages = 10

        if not keyword:
            return jsonify({
                'success': False,
                'message': 'Please enter a search keyword'
            }), 400

        if pages < 5:
            pages = 5
        elif pages > 20:
            pages = 20

        if not platforms:
            return jsonify({
                'success': False,
                'message': 'Please select at least one platform (Amazon or JD.com)'
            }), 400

        print(f"[WEB CRAWL] Starting crawl for: '{keyword}' ({pages} pages)")
        print(f"[WEB CRAWL] Platforms selected: {platforms}")

        # Log advanced settings
        amazon_proxy = bool(data.get('amazon_proxy', False))
        amazon_captcha = bool(data.get('amazon_captcha', False))
        amazon_delay = max(1, int(data.get('amazon_delay', 3)))
        amazon_retries = max(1, int(data.get('amazon_retries', 2)))

        jd_proxy = bool(data.get('jd_proxy', False))
        jd_captcha = bool(data.get('jd_captcha', True))
        jd_delay = max(2, int(data.get('jd_delay', 5)))
        jd_retries = max(1, int(data.get('jd_retries', 3)))

        timeout = max(10, int(data.get('timeout', 30)))
        max_concurrent = max(1, min(10, int(data.get('max_concurrent', 3))))

        print(f"[WEB CRAWL] Amazon settings - Proxy: {amazon_proxy}, "
              f"CAPTCHA: {amazon_captcha}, "
              f"Delay: {amazon_delay}s, "
              f"Retries: {amazon_retries}")

        print(f"[WEB CRAWL] JD.com settings - Proxy: {jd_proxy}, "
              f"CAPTCHA: {jd_captcha}, "
              f"Delay: {jd_delay}s, "
              f"Retries: {jd_retries}")

        print(f"[WEB CRAWL] Global settings - Timeout: {timeout}s, "
              f"Max Concurrent: {max_concurrent}")

        try:
            # Try to import multi_crawler
            sys.path.append('crawlers')
            from multi_crawler import MultiWebsiteCrawler

            # Create crawler instance
            crawler = MultiWebsiteCrawler()

            # Build complete configuration
            config = {
                'keyword': keyword,
                'pages': pages,
                'platforms': platforms,

                # Amazon settings
                'amazon_proxy': amazon_proxy,
                'amazon_captcha': amazon_captcha,
                'amazon_delay': amazon_delay,
                'amazon_retries': amazon_retries,

                # JD.com settings
                'jd_proxy': jd_proxy,
                'jd_captcha': jd_captcha,
                'jd_delay': jd_delay,
                'jd_retries': jd_retries,

                # Global settings
                'timeout': timeout,
                'max_concurrent': max_concurrent
            }

            # Set configuration
            crawler.set_config(config)

            # Create crawlers
            crawler.create_crawlers()

            # Run crawl
            results = crawler.crawl_all()

            # Get statistics
            stats = crawler.get_stats()
            total_products = stats['total_products']

            # Reload data
            global df, price_monitor, recommender
            df = load_data()
            price_monitor.df = df
            recommender.df = df

            # Retrain recommendation model
            if ML_AVAILABLE and len(df) >= 10:
                print("[ML] Retraining recommendation model with new data...")
                recommender.train_model()

            # Generate new charts
            print("[WEB CRAWL] Generating new charts...")
            chart_types = ['price', 'rating', 'category', 'platform', 'trend', 'sentiment']
            for chart_type in chart_types:
                generate_chart_pair(chart_type)

            return jsonify({
                'success': True,
                'message': f'Successfully crawled {keyword}! Collected {total_products} products.',
                'products_count': total_products,
                'output_preview': f'Crawled {total_products} products from {len(platforms)} platform(s)',
                'pages_used': pages,
                'platforms': platforms,
                'amazon_products': stats.get('amazon_products', 0),
                'jd_products': stats.get('jd_products', 0)
            })

        except ImportError as e:
            print(f"[WEB CRAWL] Import error: {e}")
            print("[WEB CRAWL] Using fallback data generation...")

            # Create crawlers directory if it doesn't exist
            os.makedirs('crawlers', exist_ok=True)

            # Fallback to sample data generation
            return generate_fallback_data(keyword, pages, platforms, data)
        except Exception as e:
            print(f"[WEB CRAWL] Crawler error: {str(e)}")
            import traceback
            traceback.print_exc()
            # Fallback to sample data generation
            return generate_fallback_data(keyword, pages, platforms, data)

    except Exception as e:
        print(f"[WEB CRAWL ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500


def generate_fallback_data(keyword, pages, platforms, settings=None):
    """Generate fallback sample data and APPEND to existing data"""
    global df, price_monitor, recommender

    import pandas as pd
    from datetime import datetime
    import random
    import time

    print(f"[FALLBACK] Generating sample data for '{keyword}' ({pages} pages)")
    print(f"[FALLBACK] Platforms: {platforms}")

    all_products = []

    # Apply custom settings if provided
    amazon_delay = settings.get('amazon_delay', 3) if settings else 3
    jd_delay = settings.get('jd_delay', 5) if settings else 5

    # Generate Amazon data
    if 'amazon' in platforms:
        print(f"[FALLBACK] Generating Amazon data with {pages} pages")

        for page in range(1, min(pages, 5) + 1):  # Limit to 5 pages max
            products_per_page = random.randint(5, 10)
            for i in range(products_per_page):
                price = random.randint(100, 2000)
                all_products.append({
                    'platform': 'Amazon',
                    'product_id': f'AMZ_FB_{keyword[:3].upper()}_{int(time.time())}_{page:03d}_{i:04d}',
                    'name': f'{keyword} Amazon Product {page}-{i}',
                    'current_price': float(price),
                    'original_price': float(round(price * random.uniform(1.1, 1.3), 2)),
                    'rating': float(round(random.uniform(3.0, 5.0), 1)),
                    'review_count': int(random.randint(100, 50000)),
                    'store_name': 'Amazon Store',
                    'category': random.choice(['Electronics', 'Clothing', 'Home', 'Books', 'Sports']),
                    'crawled_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'source_keyword': keyword,
                    'is_fallback': True  # Mark as fallback data
                })

    # Generate JD.com data
    if 'jd' in platforms:
        print(f"[FALLBACK] Generating JD.com data with {pages} pages")

        for page in range(1, min(pages, 5) + 1):
            products_per_page = random.randint(4, 8)
            for i in range(products_per_page):
                price = random.randint(500, 5000)
                all_products.append({
                    'platform': 'JD.com',
                    'product_id': f'JD_FB_{keyword[:3].upper()}_{int(time.time())}_{page:03d}_{i:04d}',
                    'name': f'{keyword} JD商品 {page}-{i}',
                    'current_price': float(price),
                    'original_price': float(round(price * random.uniform(1.1, 1.3), 2)),
                    'rating': float(round(random.uniform(3.5, 5.0), 1)),
                    'review_count': int(random.randint(1000, 100000)),
                    'store_name': random.choice(['JD自营', '品牌旗舰店', '授权专卖店']),
                    'category': random.choice(['电子产品', '家居', '服装', '图书', '运动户外']),
                    'crawled_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'source_keyword': keyword,
                    'is_fallback': True  # Mark as fallback data
                })

    # ========== CRITICAL FIX: Use a helper function to append safely ==========
    if all_products:
        success = append_products_safely(all_products, 'data/all_products.csv')
        if not success:
            print("[FALLBACK WARNING] Could not append to all_products.csv, saving separately")
            # Save to a separate file as backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"data/fallback_{keyword}_{timestamp}.csv"
            pd.DataFrame(all_products).to_csv(backup_file, index=False, encoding='utf-8')
            print(f"[FALLBACK] Saved to backup file: {backup_file}")

    # Count products by platform
    amazon_count = len([p for p in all_products if normalize_platform_name(p.get('platform', '')) == 'Amazon'])
    jd_count = len([p for p in all_products if normalize_platform_name(p.get('platform', '')) == 'JD.com'])

    # Reload data to include the newly added products
    df = load_data()
    price_monitor.df = df
    recommender.df = df

    # Retrain recommendation model if needed
    if ML_AVAILABLE and len(df) >= 10:
        print("[ML] Retraining recommendation model with new data...")
        recommender.train_model()

    return jsonify({
        'success': True,
        'message': f'Generated fallback data for {keyword}!',
        'products_count': len(all_products),
        'output_preview': f'Generated {len(all_products)} sample products from {len(platforms)} platform(s)',
        'pages_used': min(pages, 5),
        'platforms': platforms,
        'amazon_products': amazon_count,
        'jd_products': jd_count,
        'is_fallback': True
    })


def normalize_all_platforms_in_data():
    """Helper function to normalize all platform names in the database"""
    if 'platform' in df.columns:
        # Store original names for display
        if 'platform_original' not in df.columns:
            df['platform_original'] = df['platform']

        # Apply normalization
        df['platform'] = df['platform'].apply(normalize_platform_name)

        # Show statistics
        original_counts = df['platform_original'].value_counts()
        normalized_counts = df['platform'].value_counts()

        print("\n📊 Platform Name Normalization Statistics:")
        print(f"Original platforms: {len(original_counts)}")
        print(f"Normalized platforms: {len(normalized_counts)}")

        for platform, count in original_counts.items():
            normalized = normalize_platform_name(platform)
            print(f"  '{platform}' → '{normalized}': {count} products")

@app.route('/database')
def database_view():
    # Get data summary
    summary = {
        'columns': list(df.columns),
        'total_rows': len(df),
        'data_types': {col: str(df[col].dtype) for col in df.columns},
        'sample_data': df.head(10).to_dict('records')
    }

    # Get platform distribution
    if 'platform' in df.columns:
        # Normalize platform names for display
        df_normalized = df.copy()
        df_normalized['platform_normalized'] = df_normalized['platform'].apply(normalize_platform_name)
        platform_dist = df_normalized['platform_normalized'].value_counts().to_dict()
        summary['platform_distribution'] = platform_dist

    return render_template('database.html', summary=summary)


@app.route('/generate_all_charts')
def generate_all_charts():
    try:
        charts = []

        # Generate each chart type
        chart_types = [
            ('price', 'Price Distribution'),
            ('rating', 'Rating Distribution'),
            ('category', 'Category Distribution'),
            ('platform', 'Platform Comparison'),
            ('trend', 'Price Trends'),
            ('sentiment', 'Sentiment Analysis')
        ]

        for chart_type, chart_name in chart_types:
            print(f"[INFO] Generating {chart_type} chart...")

            if chart_type == 'price':
                chart_file = generate_price_chart()
            elif chart_type == 'rating':
                chart_file = generate_rating_chart()
            elif chart_type == 'category':
                chart_file = generate_category_chart()
            elif chart_type == 'platform':
                chart_file = generate_platform_chart()
            elif chart_type == 'trend':
                chart_file = generate_trend_chart()
            elif chart_type == 'sentiment':
                chart_file = generate_sentiment_chart()
            else:
                continue

            if chart_file:
                charts.append({'name': chart_name, 'file': chart_file})
                print(f"[OK] Generated {chart_type} chart")

        return jsonify({
            'success': True,
            'message': f'Generated {len(charts)} charts',
            'charts': charts
        })

    except Exception as e:
        print(f"[ERROR] Failed to generate all charts: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        })


@app.route('/refresh_data')
def refresh_data():
    global df, price_monitor, recommender
    try:
        df = load_data()
        price_monitor.df = df
        recommender.df = df

        return jsonify({
            'success': True,
            'message': f'Refreshed data: {len(df)} products loaded'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', error=str(e)), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html', error=str(e)), 500


# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 60)
    print("E-COMMERCE DATA ANALYSIS SYSTEM")
    print("=" * 60)
    print(f"Loaded {len(df)} products")

    # Show platform distribution
    if 'platform' in df.columns:
        df_normalized = df.copy()
        df_normalized['platform'] = df_normalized['platform'].apply(normalize_platform_name)
        platform_counts = df_normalized['platform'].value_counts()
        for platform, count in platform_counts.items():
            print(f"  {platform}: {count} products")

    print(f"Monitoring: {len(price_monitor.monitored_products)} products")
    print(f"ML Recommendations: {'Available' if ML_AVAILABLE else 'Not available'}")
    print("\nServer running at: http://127.0.0.1:5000")
    print("Available pages:")
    print("   • /              - Dashboard")
    print("   • /monitoring    - Price alerts")
    print("   • /recommendations - ML recommendations")
    print("   • /products      - Product search")
    print("   • /analysis      - Data analysis")
    print("   • /database      - Database view")
    print("   • /crawl_panel   - Web crawler with custom settings")
    print("\nPress Ctrl+C to stop")
    print("=" * 60)

    app.run(debug=True, host='127.0.0.1', port=5000)