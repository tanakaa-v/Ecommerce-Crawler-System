import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional
import json
import os
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')
import sys

# Try to import for sentiment analysis
try:
    from textblob import TextBlob

    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False
    print("⚠️ TextBlob not installed. Sentiment analysis will be limited.")
    print("   Install with: pip install textblob")

try:
    from snownlp import SnowNLP

    SNOWNLP_AVAILABLE = True
except ImportError:
    SNOWNLP_AVAILABLE = False
    print("⚠️ SnowNLP not installed. Chinese sentiment analysis will be limited.")
    print("   Install with: pip install snownlp")


class DataAnalyzer:
    #Complete Data Analysis Module for E-commerce Data

    def __init__(self, data_source='data/all_products.csv', use_database=False):
        #Initialize analyzer with data source

        #Args:
            #data_source: CSV file path or database connection
            #use_database: If True, connect to MySQL database

        print("=" * 60)
        print("📊 E-COMMERCE DATA ANALYSIS MODULE")
        print("=" * 60)

        self.data_source = data_source
        self.use_database = use_database
        self.df = None
        self.analysis_results = {}

        # Create output directory for charts
        os.makedirs('analysis_output', exist_ok=True)
        os.makedirs('analysis_output/charts', exist_ok=True)

        # Load data
        self.load_data()

    def load_data(self):
        #Load data from CSV or database
        print("\n📥 LOADING DATA...")

        try:
            if self.use_database:
                # Load from MySQL database
                self._load_from_database()
            else:
                # Load from CSV
                if os.path.exists(self.data_source):
                    self.df = pd.read_csv(self.data_source, encoding='utf-8')
                    print(f"✅ Loaded {len(self.df)} products from {self.data_source}")
                else:
                    print(f"❌ Data file not found: {self.data_source}")
                    print("   Creating sample data for demonstration...")
                    self._create_sample_data()

            if self.df is not None and not self.df.empty:
                self._clean_data()
                self._show_data_summary()
            else:
                print("⚠️ No data available for analysis")

        except Exception as e:
            print(f"❌ Error loading data: {e}")
            print("   Creating sample data for demonstration...")
            self._create_sample_data()

    def _load_from_database(self):
        #Load data from MySQL database
        try:
            from database import MySQLDatabase

            db = MySQLDatabase()
            if db.connect():
                # Get all products
                products = db.search_products(limit=1000)
                self.df = pd.DataFrame(products)

                if not self.df.empty:
                    print(f"✅ Loaded {len(self.df)} products from database")
                else:
                    print("⚠️ No products in database")

                db.close()
            else:
                print("❌ Could not connect to database")

        except ImportError:
            print("⚠️ Database module not available, using CSV")
            if os.path.exists(self.data_source):
                self.df = pd.read_csv(self.data_source, encoding='utf-8')

    def _create_sample_data(self):
        #Create sample data for demonstration
        print("📝 Creating sample analysis data...")

        # Sample data for demonstration
        np.random.seed(42)

        platforms = ['Amazon', 'JD.com']
        brands = ['Apple', 'Samsung', 'Huawei', 'Xiaomi', 'Dell', 'Lenovo', 'HP', 'Sony']
        categories = ['Laptop', 'Phone', 'Tablet', 'Headphones', 'Monitor', 'Accessories']

        data = []
        for i in range(100):
            platform = np.random.choice(platforms, p=[0.6, 0.4])
            brand = np.random.choice(brands)
            category = np.random.choice(categories)

            # Price based on brand and category
            base_price = {'Apple': 1200, 'Samsung': 800, 'Huawei': 600,
                          'Xiaomi': 400, 'Dell': 900, 'Lenovo': 700,
                          'HP': 850, 'Sony': 750}[brand]

            category_multiplier = {'Laptop': 1.5, 'Phone': 1.0, 'Tablet': 0.8,
                                   'Headphones': 0.3, 'Monitor': 1.2, 'Accessories': 0.4}

            current_price = base_price * category_multiplier[category] * np.random.uniform(0.8, 1.2)
            original_price = current_price * np.random.uniform(1.1, 1.3)

            # Generate review text for sentiment analysis
            review_texts = [
                f"Great {category} from {brand}. Very satisfied with the quality!",
                f"Average product. Does what it says but nothing special.",
                f"Disappointing. Expected better from {brand}.",
                f"Excellent value for money. Highly recommended!",
                f"Poor quality. Stopped working after a week.",
                f"Best {category} I've ever owned. Worth every penny!",
                f"Mediocre performance. Would not buy again.",
                f"Outstanding! Exceeded all my expectations."
            ]

            data.append({
                'platform': platform,
                'product_id': f'{platform[:2].upper()}_{i:04d}',
                'name': f'{brand} {category} Model {i}',
                'current_price': round(current_price, 2),
                'original_price': round(original_price, 2),
                'rating': round(np.random.uniform(3.0, 5.0), 1),
                'review_count': np.random.randint(10, 10000),
                'store_name': f'{brand} Official Store',
                'category': category,
                'details': json.dumps(
                    {'brand': brand, 'color': np.random.choice(['Black', 'White', 'Blue', 'Silver'])}),
                'review_text': np.random.choice(review_texts),
                'crawled_at': (datetime.now() - timedelta(days=np.random.randint(0, 30))).strftime('%Y-%m-%d %H:%M:%S')
            })

        self.df = pd.DataFrame(data)
        print(f"✅ Created {len(self.df)} sample products for analysis")

    def _clean_data(self):
        #Clean and prepare data for analysis
        print("🧹 Cleaning data...")

        # Ensure numeric columns
        numeric_cols = ['current_price', 'original_price', 'rating', 'review_count']
        for col in numeric_cols:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')

        # Fill missing values
        if 'current_price' in self.df.columns:
            self.df['current_price'].fillna(self.df['current_price'].median(), inplace=True)

        if 'rating' in self.df.columns:
            self.df['rating'].fillna(self.df['rating'].median(), inplace=True)

        if 'review_count' in self.df.columns:
            self.df['review_count'].fillna(0, inplace=True)

        # Extract brand from name (simple extraction)
        if 'name' in self.df.columns:
            brand_keywords = ['Apple', 'Samsung', 'Huawei', 'Xiaomi', 'Dell',
                              'Lenovo', 'HP', 'Sony', 'Microsoft', 'Google']

            def extract_brand(name):
                if isinstance(name, str):
                    for brand in brand_keywords:
                        if brand.lower() in name.lower():
                            return brand
                return 'Other'

            self.df['brand'] = self.df['name'].apply(extract_brand)

        # Calculate discount percentage
        if 'current_price' in self.df.columns and 'original_price' in self.df.columns:
            self.df['discount_pct'] = ((self.df['original_price'] - self.df['current_price']) /
                                       self.df['original_price'].replace(0, 1)) * 100

        print("✅ Data cleaning complete")

    def _show_data_summary(self):
        #Show summary of loaded data
        print("\n📋 DATA SUMMARY:")
        print("-" * 40)

        if self.df is not None and not self.df.empty:
            print(f"Total products: {len(self.df)}")

            if 'platform' in self.df.columns:
                platform_counts = self.df['platform'].value_counts()
                print("\nBy Platform:")
                for platform, count in platform_counts.items():
                    print(f"  {platform}: {count} products ({count / len(self.df) * 100:.1f}%)")

            if 'current_price' in self.df.columns:
                print(f"\nPrice Statistics:")
                print(f"  Min: ${self.df['current_price'].min():.2f}")
                print(f"  Max: ${self.df['current_price'].max():.2f}")
                print(f"  Avg: ${self.df['current_price'].mean():.2f}")
                print(f"  Median: ${self.df['current_price'].median():.2f}")

            if 'rating' in self.df.columns:
                print(f"\nRating Statistics:")
                print(f"  Avg Rating: {self.df['rating'].mean():.2f}/5.0")
                print(f"  Products with rating > 4: {(self.df['rating'] > 4).sum()}")

        print("-" * 40)

    # ==================== PRICE DISTRIBUTION ANALYSIS ====================

    def analyze_price_distribution(self, platform_filter=None):

        #Analyze price distribution

        #Args:
            #platform_filter: Filter by platform (e.g., 'Amazon', 'JD.com')

        #Returns: Dict with analysis results

        print(f"\n💰 PRICE DISTRIBUTION ANALYSIS")
        print("-" * 40)

        if self.df is None or self.df.empty:
            print("❌ No data available")
            return {}

        # Filter data if platform specified
        if platform_filter and 'platform' in self.df.columns:
            df_filtered = self.df[self.df['platform'] == platform_filter]
            print(f"Analyzing {platform_filter}: {len(df_filtered)} products")
        else:
            df_filtered = self.df
            print(f"Analyzing all platforms: {len(df_filtered)} products")

        if 'current_price' not in df_filtered.columns:
            print("❌ No price data available")
            return {}

        results = {}

        # Basic statistics
        prices = df_filtered['current_price'].dropna()
        results['count'] = len(prices)
        results['mean'] = float(prices.mean())
        results['median'] = float(prices.median())
        results['std'] = float(prices.std())
        results['min'] = float(prices.min())
        results['max'] = float(prices.max())
        results['q25'] = float(prices.quantile(0.25))
        results['q75'] = float(prices.quantile(0.75))

        # Price ranges
        price_ranges = {
            'Under $100': (prices < 100).sum(),
            '$100-$500': ((prices >= 100) & (prices < 500)).sum(),
            '$500-$1000': ((prices >= 500) & (prices < 1000)).sum(),
            '$1000-$2000': ((prices >= 1000) & (prices < 2000)).sum(),
            '$2000+': (prices >= 2000).sum()
        }
        results['price_ranges'] = price_ranges

        # Print results
        print(f"  Products analyzed: {results['count']}")
        print(f"  Average price: ${results['mean']:.2f}")
        print(f"  Median price: ${results['median']:.2f}")
        print(f"  Price range: ${results['min']:.2f} - ${results['max']:.2f}")

        print("\n  Price Distribution:")
        for range_name, count in price_ranges.items():
            percentage = (count / results['count'] * 100) if results['count'] > 0 else 0
            print(f"    {range_name}: {count} products ({percentage:.1f}%)")

        # Create visualization
        self._plot_price_distribution(df_filtered, platform_filter)

        self.analysis_results['price_distribution'] = results
        return results

    def _plot_price_distribution(self, df, platform_filter=None):
        #Create price distribution visualization
        try:
            plt.figure(figsize=(12, 5))

            # Histogram
            plt.subplot(1, 2, 1)
            plt.hist(df['current_price'].dropna(), bins=30, alpha=0.7, color='skyblue', edgecolor='black')
            plt.title(f'Price Distribution{" - " + platform_filter if platform_filter else ""}')
            plt.xlabel('Price ($)')
            plt.ylabel('Number of Products')
            plt.grid(True, alpha=0.3)

            # Box plot
            plt.subplot(1, 2, 2)
            box_data = []
            box_labels = []

            if 'platform' in df.columns:
                # Box plot by platform
                platforms = df['platform'].unique()
                for platform in platforms:
                    platform_prices = df[df['platform'] == platform]['current_price'].dropna()
                    if len(platform_prices) > 0:
                        box_data.append(platform_prices)
                        box_labels.append(platform)
            else:
                # Single box plot
                box_data = [df['current_price'].dropna()]
                box_labels = ['All Products']

            plt.boxplot(box_data, labels=box_labels)
            plt.title('Price Distribution by Platform')
            plt.ylabel('Price ($)')
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)

            plt.tight_layout()

            # Save figure
            filename = f"analysis_output/charts/price_distribution"
            if platform_filter:
                filename += f"_{platform_filter.lower()}"
            filename += ".png"

            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"  📈 Chart saved: {filename}")
            plt.close()

        except Exception as e:
            print(f"  ⚠️ Error creating chart: {e}")

    # ==================== SENTIMENT ANALYSIS ====================

    def analyze_sentiment(self, text_column='review_text', platform_filter=None):

        #Perform sentiment analysis on text data

        #Args:
            #text_column: Column containing text to analyze
            #platform_filter: Filter by platform

        #Returns: Dict with sentiment analysis results

        print(f"\n😊 SENTIMENT ANALYSIS")
        print("-" * 40)

        if self.df is None or self.df.empty:
            print("❌ No data available")
            return {}

        # Filter data if platform specified
        if platform_filter and 'platform' in self.df.columns:
            df_filtered = self.df[self.df['platform'] == platform_filter]
        else:
            df_filtered = self.df

        if text_column not in df_filtered.columns:
            print(f"❌ Text column '{text_column}' not found in data")
            print("   Creating sample review text for demonstration...")
            self._add_sample_review_text(df_filtered)

            if text_column not in df_filtered.columns:
                return {}

        results = {
            'total_texts': 0,
            'sentiment_scores': [],
            'sentiment_categories': {'positive': 0, 'neutral': 0, 'negative': 0},
            'avg_sentiment': 0
        }

        sentiments = []

        print(f"  Analyzing {len(df_filtered)} products...")

        for idx, row in df_filtered.iterrows():
            text = row.get(text_column, '')

            if pd.isna(text) or not isinstance(text, str) or len(text.strip()) < 3:
                continue

            sentiment_score = self._get_sentiment_score(text)
            sentiments.append(sentiment_score)

            # Categorize
            if sentiment_score > 0.3:
                results['sentiment_categories']['positive'] += 1
            elif sentiment_score < -0.3:
                results['sentiment_categories']['negative'] += 1
            else:
                results['sentiment_categories']['neutral'] += 1

        if sentiments:
            results['total_texts'] = len(sentiments)
            results['sentiment_scores'] = sentiments
            results['avg_sentiment'] = float(np.mean(sentiments))

            # Print results
            print(f"  Texts analyzed: {results['total_texts']}")
            print(f"  Average sentiment: {results['avg_sentiment']:.3f}")
            print(f"  Positive: {results['sentiment_categories']['positive']} "
                  f"({results['sentiment_categories']['positive'] / results['total_texts'] * 100:.1f}%)")
            print(f"  Neutral: {results['sentiment_categories']['neutral']} "
                  f"({results['sentiment_categories']['neutral'] / results['total_texts'] * 100:.1f}%)")
            print(f"  Negative: {results['sentiment_categories']['negative']} "
                  f"({results['sentiment_categories']['negative'] / results['total_texts'] * 100:.1f}%)")

            # Create visualization
            self._plot_sentiment_analysis(results, platform_filter)
        else:
            print("  ⚠️ No valid text data for sentiment analysis")

        self.analysis_results['sentiment'] = results
        return results

    def _get_sentiment_score(self, text):
        #Get sentiment score for text (positive, neutral, negative)
        # Simple rule-based sentiment as fallback
        positive_words = ['great', 'excellent', 'good', 'best', 'love', 'awesome',
                          'perfect', 'recommend', 'happy', 'satisfied', 'amazing']
        negative_words = ['bad', 'poor', 'terrible', 'disappointing', 'worst',
                          'avoid', 'waste', 'broken', 'defective', 'useless']

        # Count positive and negative words
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        # Simple sentiment calculation
        if positive_count > negative_count:
            return 0.5 + (positive_count - negative_count) * 0.1
        elif negative_count > positive_count:
            return -0.5 - (negative_count - positive_count) * 0.1
        else:
            return 0.0

    def _add_sample_review_text(self, df):
        #Add sample review text for sentiment analysis demonstration
        sample_reviews = [
            "Excellent product, very satisfied with the quality!",
            "Good value for money, works as expected.",
            "Average product, nothing special.",
            "Disappointing quality, expected better.",
            "Waste of money, stopped working after a week.",
            "Outstanding performance, highly recommended!",
            "Mediocre at best, would not buy again.",
            "Perfect for my needs, very happy with purchase.",
            "Poor build quality, not worth the price.",
            "Amazing features, exceeded my expectations!"
        ]

        if 'review_text' not in df.columns:
            df['review_text'] = np.random.choice(sample_reviews, size=len(df))
            print("  Added sample review text for analysis")

    def _plot_sentiment_analysis(self, results, platform_filter=None):
        #Create sentiment analysis visualization
        try:
            plt.figure(figsize=(10, 5))

            # Pie chart for sentiment categories
            plt.subplot(1, 2, 1)
            categories = ['Positive', 'Neutral', 'Negative']
            counts = [
                results['sentiment_categories']['positive'],
                results['sentiment_categories']['neutral'],
                results['sentiment_categories']['negative']
            ]
            colors = ['lightgreen', 'lightblue', 'lightcoral']

            plt.pie(counts, labels=categories, colors=colors, autopct='%1.1f%%', startangle=90)
            plt.title(f'Sentiment Distribution{" - " + platform_filter if platform_filter else ""}')

            # Histogram of sentiment scores
            plt.subplot(1, 2, 2)
            plt.hist(results['sentiment_scores'], bins=20, alpha=0.7, color='purple', edgecolor='black')
            plt.axvline(x=results['avg_sentiment'], color='red', linestyle='--',
                        label=f'Average: {results["avg_sentiment"]:.3f}')
            plt.title('Sentiment Scores Distribution')
            plt.xlabel('Sentiment Score (-1 to 1)')
            plt.ylabel('Frequency')
            plt.legend()
            plt.grid(True, alpha=0.3)

            plt.tight_layout()

            # Save figure
            filename = f"analysis_output/charts/sentiment_analysis"
            if platform_filter:
                filename += f"_{platform_filter.lower()}"
            filename += ".png"

            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"  📈 Chart saved: {filename}")
            plt.close()

        except Exception as e:
            print(f"  ⚠️ Error creating chart: {e}")

    # ==================== BRAND/CATEGORY STATISTICS ====================

    def analyze_brand_category_stats(self, platform_filter=None):

        #Analyze brand and category statistics
        #Returns: Dict with brand and category analysis

        print(f"\n🏷️ BRAND & CATEGORY STATISTICS")
        print("-" * 40)

        if self.df is None or self.df.empty:
            print("❌ No data available")
            return {}

        # Filter data if platform specified
        if platform_filter and 'platform' in self.df.columns:
            df_filtered = self.df[self.df['platform'] == platform_filter]
            print(f"Analyzing {platform_filter}: {len(df_filtered)} products")
        else:
            df_filtered = self.df
            print(f"Analyzing all platforms: {len(df_filtered)} products")

        results = {
            'brand_stats': {},
            'category_stats': {},
            'platform_comparison': {}
        }

        # Brand analysis
        if 'brand' in df_filtered.columns:
            brand_stats = df_filtered.groupby('brand').agg({
                'current_price': ['count', 'mean', 'median', 'min', 'max'],
                'rating': 'mean',
                'review_count': 'sum'
            }).round(2)

            brand_stats.columns = ['product_count', 'avg_price', 'median_price',
                                   'min_price', 'max_price', 'avg_rating', 'total_reviews']

            results['brand_stats'] = brand_stats.to_dict('index')

            print("\n  Top Brands by Product Count:")
            top_brands = brand_stats['product_count'].sort_values(ascending=False).head(5)
            for brand, count in top_brands.items():
                avg_price = brand_stats.loc[brand, 'avg_price']
                print(f"    {brand}: {count} products, avg ${avg_price:.2f}")

        # Category analysis
        if 'category' in df_filtered.columns:
            category_stats = df_filtered.groupby('category').agg({
                'current_price': ['count', 'mean', 'median'],
                'rating': 'mean'
            }).round(2)

            category_stats.columns = ['product_count', 'avg_price', 'median_price', 'avg_rating']
            results['category_stats'] = category_stats.to_dict('index')

            print("\n  Categories by Product Count:")
            top_categories = category_stats['product_count'].sort_values(ascending=False).head(5)
            for category, count in top_categories.items():
                avg_price = category_stats.loc[category, 'avg_price']
                print(f"    {category}: {count} products, avg ${avg_price:.2f}")

        # Platform comparison (if multiple platforms)
        if 'platform' in df_filtered.columns and len(df_filtered['platform'].unique()) > 1:
            platform_stats = df_filtered.groupby('platform').agg({
                'current_price': ['count', 'mean', 'median'],
                'rating': 'mean',
                'review_count': 'sum'
            }).round(2)

            platform_stats.columns = ['product_count', 'avg_price', 'median_price',
                                      'avg_rating', 'total_reviews']
            results['platform_comparison'] = platform_stats.to_dict('index')

        # Create visualizations
        self._plot_brand_category_stats(df_filtered, platform_filter)

        self.analysis_results['brand_category_stats'] = results
        return results

    def _plot_brand_category_stats(self, df, platform_filter=None):
        #Create brand and category visualization
        try:
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))

            # 1. Top brands by product count
            if 'brand' in df.columns:
                brand_counts = df['brand'].value_counts().head(10)
                axes[0, 0].barh(brand_counts.index, brand_counts.values, color='skyblue')
                axes[0, 0].set_title('Top 10 Brands by Product Count')
                axes[0, 0].set_xlabel('Number of Products')
                axes[0, 0].invert_yaxis()

            # 2. Top categories by product count
            if 'category' in df.columns:
                category_counts = df['category'].value_counts().head(10)
                axes[0, 1].bar(category_counts.index, category_counts.values, color='lightcoral')
                axes[0, 1].set_title('Top Categories by Product Count')
                axes[0, 1].set_ylabel('Number of Products')
                axes[0, 1].tick_params(axis='x', rotation=45)

            # 3. Average price by brand (top 10)
            if 'brand' in df.columns and 'current_price' in df.columns:
                brand_avg_price = df.groupby('brand')['current_price'].mean().sort_values(ascending=False).head(10)
                axes[1, 0].bar(brand_avg_price.index, brand_avg_price.values, color='lightgreen')
                axes[1, 0].set_title('Top 10 Brands by Average Price')
                axes[1, 0].set_ylabel('Average Price ($)')
                axes[1, 0].tick_params(axis='x', rotation=45)

            # 4. Platform comparison (if multiple platforms)
            if 'platform' in df.columns and len(df['platform'].unique()) > 1:
                platform_data = []
                platform_labels = []

                for platform in df['platform'].unique():
                    platform_prices = df[df['platform'] == platform]['current_price'].dropna()
                    if len(platform_prices) > 0:
                        platform_data.append(platform_prices)
                        platform_labels.append(platform)

                if platform_data:
                    axes[1, 1].boxplot(platform_data, labels=platform_labels)
                    axes[1, 1].set_title('Price Distribution by Platform')
                    axes[1, 1].set_ylabel('Price ($)')
                    axes[1, 1].grid(True, alpha=0.3)

            plt.tight_layout()

            # Save figure
            filename = f"analysis_output/charts/brand_category_stats"
            if platform_filter:
                filename += f"_{platform_filter.lower()}"
            filename += ".png"

            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"  📈 Chart saved: {filename}")
            plt.close()

        except Exception as e:
            print(f"  ⚠️ Error creating chart: {e}")

    # ==================== PRICE TREND ANALYSIS ====================

    def analyze_price_trends(self, days_back=30):

        #Analyze price trends over time

        #Args:
            #days_back: Number of days to look back

        #Returns: Dict with price trend analysis

        print(f"\n📈 PRICE TREND ANALYSIS (Last {days_back} days)")
        print("-" * 40)

        if self.df is None or self.df.empty:
            print("❌ No data available")
            return {}

        # For demonstration, we'll create simulated price history
        # In real scenario, you would query the price_history table from database
        results = self._simulate_price_trends(days_back)

        # Print summary
        if results['trend_analysis']:
            print("  Price Trend Summary:")
            for platform, trend in results['trend_analysis'].items():
                direction = "↑ Increasing" if trend['trend'] > 0.01 else "↓ Decreasing" if trend[
                                                                                               'trend'] < -0.01 else "→ Stable"
                print(f"    {platform}: {direction} ({trend['trend'] * 100:.1f}% change)")

        # Create visualization
        self._plot_price_trends(results)

        self.analysis_results['price_trends'] = results
        return results

    def _simulate_price_trends(self, days_back):
        #Simulate price trends for demonstration
        # In a real system, this would query the price_history table
        # For now, we create simulated data

        results = {
            'total_products_tracked': 0,
            'days_analyzed': days_back,
            'trend_analysis': {},
            'sample_trend_data': {}
        }

        # Simulate trends for each platform
        platforms = self.df['platform'].unique() if 'platform' in self.df.columns else ['All']

        for platform in platforms:
            # Simulate price change trend
            trend = np.random.uniform(-0.1, 0.1)  # -10% to +10% change

            # Generate sample time series data
            dates = pd.date_range(end=datetime.now(), periods=days_back, freq='D')
            base_price = 500  # Base price

            # Add some random variation
            prices = []
            for i in range(days_back):
                day_trend = trend * (i / days_back)  # Linear trend
                random_variation = np.random.uniform(-0.05, 0.05)  # Random daily variation
                price = base_price * (1 + day_trend + random_variation)
                prices.append(round(price, 2))

            results['trend_analysis'][platform] = {
                'trend': trend,
                'current_avg_price': prices[-1],
                'previous_avg_price': prices[0],
                'percent_change': ((prices[-1] - prices[0]) / prices[0]) * 100
            }

            results['sample_trend_data'][platform] = {
                'dates': dates.strftime('%Y-%m-%d').tolist(),
                'prices': prices
            }

        results['total_products_tracked'] = len(self.df)
        return results

    def _plot_price_trends(self, results):
        """Create price trend visualization"""
        try:
            plt.figure(figsize=(12, 8))

            # Plot for each platform
            platforms = list(results['sample_trend_data'].keys())

            for i, platform in enumerate(platforms, 1):
                plt.subplot(2, 2, i)

                data = results['sample_trend_data'][platform]
                dates = pd.to_datetime(data['dates'])
                prices = data['prices']

                plt.plot(dates, prices, marker='o', linewidth=2, markersize=4)
                plt.title(f'{platform} Price Trends')
                plt.xlabel('Date')
                plt.ylabel('Average Price ($)')
                plt.grid(True, alpha=0.3)
                plt.xticks(rotation=45)

                # Add trend line
                z = np.polyfit(range(len(prices)), prices, 1)
                p = np.poly1d(z)
                plt.plot(dates, p(range(len(prices))), 'r--', alpha=0.7, label='Trend Line')
                plt.legend()

                # Stop if we have 4 subplots
                if i >= 4:
                    break

            plt.tight_layout()

            # Save figure
            filename = f"analysis_output/charts/price_trends.png"
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"  📈 Chart saved: {filename}")
            plt.close()

        except Exception as e:
            print(f"  ⚠️ Error creating chart: {e}")

    # ==================== COMPREHENSIVE ANALYSIS ====================

    def run_comprehensive_analysis(self):
        #Run all analysis modules and generate report
        print("\n" + "=" * 60)
        print("🎯 RUNNING COMPREHENSIVE ANALYSIS")
        print("=" * 60)

        # Run all analyses
        self.analyze_price_distribution()
        self.analyze_sentiment()
        self.analyze_brand_category_stats()
        self.analyze_price_trends()

        # Generate report
        self.generate_analysis_report()

        print("\n" + "=" * 60)
        print("✅ ANALYSIS COMPLETE")
        print("=" * 60)

        return self.analysis_results

    def generate_analysis_report(self):
        #Generate comprehensive analysis report
        print("\n📄 GENERATING ANALYSIS REPORT")
        print("-" * 40)

        report_content = []
        report_content.append("=" * 60)
        report_content.append("📊 E-COMMERCE DATA ANALYSIS REPORT")
        report_content.append("=" * 60)
        report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_content.append(f"Data Source: {self.data_source}")
        report_content.append(f"Total Products: {len(self.df) if self.df is not None else 0}")
        report_content.append("")

        # Add results from each analysis
        if 'price_distribution' in self.analysis_results:
            results = self.analysis_results['price_distribution']
            report_content.append("💰 PRICE DISTRIBUTION ANALYSIS")
            report_content.append("-" * 40)
            report_content.append(f"Products Analyzed: {results.get('count', 0)}")
            report_content.append(f"Average Price: ${results.get('mean', 0):.2f}")
            report_content.append(f"Price Range: ${results.get('min', 0):.2f} - ${results.get('max', 0):.2f}")
            report_content.append("")

        if 'sentiment' in self.analysis_results:
            results = self.analysis_results['sentiment']
            report_content.append("😊 SENTIMENT ANALYSIS")
            report_content.append("-" * 40)
            report_content.append(f"Texts Analyzed: {results.get('total_texts', 0)}")
            report_content.append(f"Average Sentiment: {results.get('avg_sentiment', 0):.3f}")
            report_content.append(f"Positive: {results.get('sentiment_categories', {}).get('positive', 0)}")
            report_content.append(f"Neutral: {results.get('sentiment_categories', {}).get('neutral', 0)}")
            report_content.append(f"Negative: {results.get('sentiment_categories', {}).get('negative', 0)}")
            report_content.append("")

        if 'brand_category_stats' in self.analysis_results:
            results = self.analysis_results['brand_category_stats']
            report_content.append("🏷️ BRAND & CATEGORY STATISTICS")
            report_content.append("-" * 40)

            if results.get('brand_stats'):
                report_content.append("Top Brands:")
                for brand, stats in list(results['brand_stats'].items())[:5]:
                    report_content.append(f"  {brand}: {stats.get('product_count', 0)} products, "
                                          f"avg ${stats.get('avg_price', 0):.2f}")

            if results.get('category_stats'):
                report_content.append("\nTop Categories:")
                for category, stats in list(results['category_stats'].items())[:5]:
                    report_content.append(f"  {category}: {stats.get('product_count', 0)} products")

            report_content.append("")

        if 'price_trends' in self.analysis_results:
            results = self.analysis_results['price_trends']
            report_content.append("📈 PRICE TREND ANALYSIS")
            report_content.append("-" * 40)
            report_content.append(f"Days Analyzed: {results.get('days_analyzed', 0)}")

            if results.get('trend_analysis'):
                for platform, trend in results['trend_analysis'].items():
                    direction = "Increasing" if trend['trend'] > 0.01 else "Decreasing" if trend[
                                                                                               'trend'] < -0.01 else "Stable"
                    report_content.append(f"  {platform}: {direction} ({trend['percent_change']:.1f}% change)")

            report_content.append("")

        # Summary
        report_content.append("📋 SUMMARY")
        report_content.append("-" * 40)
        report_content.append(f"Total Analysis Modules Run: {len(self.analysis_results)}")
        report_content.append(
            f"Charts Generated: {len([f for f in os.listdir('analysis_output/charts') if f.endswith('.png')])}")
        report_content.append(f"Report Generated: analysis_output/analysis_report.txt")
        report_content.append("")
        report_content.append("=" * 60)

        # Save report
        report_file = 'analysis_output/analysis_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_content))

        print(f"✅ Report saved: {report_file}")

        # Print summary
        print("\n📊 ANALYSIS SUMMARY:")
        for line in report_content[-10:]:
            print(line)


def main():
    #Main function to run analysis module
    print("=" * 60)
    print("📊 E-COMMERCE DATA ANALYZER")
    print("=" * 60)

    # Create analyzer instance
    analyzer = DataAnalyzer(data_source='data/all_products.csv', use_database=False)

    # Run comprehensive analysis
    analyzer.run_comprehensive_analysis()

    print("\n📁 OUTPUT FILES:")
    print("-" * 40)

    # List generated files
    if os.path.exists('analysis_output'):
        for root, dirs, files in os.walk('analysis_output'):
            level = root.replace('analysis_output', '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")

    print("\n✅ Analysis module ready for integration!")

if __name__ == "__main__":
    main()

