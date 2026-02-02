# app.py - COMPLETE WORKING VERSION
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
                with open('monitoring/monitored_products.json', 'r') as f:
                    self.monitored_products = json.load(f)
        except:
            self.monitored_products = []

    def save_monitored_products(self):
        try:
            with open('monitoring/monitored_products.json', 'w') as f:
                json.dump(self.monitored_products, f, indent=2, default=str)
        except:
            pass

    def add_product_to_monitor(self, product_id: str, platform: str, target_price: float = None):
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
        self.monitored_products = [
            p for p in self.monitored_products
            if not (p['product_id'] == product_id and p['platform'] == platform)
        ]
        self.save_monitored_products()

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


# ==================== DATA LOADING ====================

def load_data():
    try:
        csv_files = [
            'data/all_products.csv',
            'data/amazon_products.csv',
            'data/jd_products.csv',
            'data/sample_products.csv'
        ]

        for csv_file in csv_files:
            if os.path.exists(csv_file):
                df = pd.read_csv(csv_file)
                print(f"[OK] Loaded {len(df)} products from {csv_file}")

                # Ensure required columns exist
                required_cols = ['product_id', 'name', 'current_price']
                for col in required_cols:
                    if col not in df.columns:
                        if col == 'current_price':
                            df['current_price'] = np.random.uniform(50, 2000, len(df))
                        elif col == 'product_id':
                            df['product_id'] = [f'PROD_{i:04d}' for i in range(len(df))]
                        elif col == 'name':
                            df['name'] = [f'Product {i}' for i in range(len(df))]

                # Add missing columns if needed
                if 'platform' not in df.columns:
                    df['platform'] = np.random.choice(['Amazon', 'JD.com'], len(df))
                if 'category' not in df.columns:
                    df['category'] = np.random.choice(['Electronics', 'Clothing', 'Home', 'Books', 'Sports'], len(df))
                if 'rating' not in df.columns:
                    df['rating'] = np.random.uniform(3.0, 5.0, len(df))
                if 'review_count' not in df.columns:
                    df['review_count'] = np.random.randint(10, 10000, len(df))

                return df

    except Exception as e:
        print(f"Error loading data: {e}")

    # Create sample data if no files found
    return create_sample_data()


def create_sample_data():
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
    df.to_csv('data/sample_products.csv', index=False)
    print(f"[OK] Created sample data with {len(df)} products")
    return df


# ==================== CHART FUNCTIONS ====================

def generate_price_chart():
    try:
        plt.figure(figsize=(10, 5))
        plt.subplot(1, 2, 1)
        prices = df['current_price'].dropna()
        plt.hist(prices, bins=30, alpha=0.7, color='steelblue', edgecolor='black')
        plt.title('Price Distribution')
        plt.xlabel('Price ($)')
        plt.ylabel('Number of Products')
        plt.grid(True, alpha=0.3)

        plt.subplot(1, 2, 2)
        if 'platform' in df.columns:
            platform_prices = df.groupby('platform')['current_price'].mean()
            bars = plt.bar(platform_prices.index, platform_prices.values)
            plt.title('Average Price by Platform')
            plt.ylabel('Average Price ($)')
            plt.xlabel('Platform')

        plt.tight_layout()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'price_distribution_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return filename

    except Exception as e:
        print(f"Error generating price chart: {e}")
        return None


def generate_rating_chart():
    try:
        plt.figure(figsize=(10, 5))
        plt.subplot(1, 2, 1)
        if 'rating' in df.columns:
            ratings = df['rating'].dropna()
            plt.hist(ratings, bins=20, alpha=0.7, color='gold', edgecolor='black')
            plt.title('Rating Distribution')
            plt.xlabel('Rating (1-5)')
            plt.ylabel('Number of Products')
            plt.grid(True, alpha=0.3)

        plt.subplot(1, 2, 2)
        if 'rating' in df.columns and 'current_price' in df.columns:
            plt.scatter(df['rating'], df['current_price'], alpha=0.6, c='purple')
            plt.title('Rating vs Price')
            plt.xlabel('Rating')
            plt.ylabel('Price ($)')
            plt.grid(True, alpha=0.3)

        plt.tight_layout()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'rating_distribution_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return filename

    except Exception as e:
        print(f"Error generating rating chart: {e}")
        return None


def generate_category_chart():
    try:
        plt.figure(figsize=(12, 6))
        if 'category' in df.columns:
            category_counts = df['category'].value_counts().head(10)

            plt.subplot(1, 2, 1)
            bars = plt.barh(category_counts.index, category_counts.values)
            plt.title('Top Product Categories')
            plt.xlabel('Number of Products')
            plt.gca().invert_yaxis()

            plt.subplot(1, 2, 2)
            plt.pie(category_counts.values, labels=category_counts.index, autopct='%1.1f%%', startangle=90)
            plt.title('Category Distribution')

        plt.tight_layout()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'category_distribution_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return filename

    except Exception as e:
        print(f"Error generating category chart: {e}")
        return None


# ==================== CREATE ERROR PAGES ====================

def create_error_pages():
    if not os.path.exists('templates/404.html'):
        with open('templates/404.html', 'w') as f:
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
        with open('templates/500.html', 'w') as f:
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


@app.route('/')
def index():
    # Generate a chart for the homepage
    price_chart = generate_price_chart()

    stats = {
        'total_products': len(df),
        'avg_price': float(df['current_price'].mean()) if 'current_price' in df.columns else 0,
        'avg_rating': float(df['rating'].mean()) if 'rating' in df.columns else 0,
        'platform_count': df['platform'].nunique() if 'platform' in df.columns else 0,
        'category_count': df['category'].nunique() if 'category' in df.columns else 0,
        'monitored_products': len(price_monitor.monitored_products),
        'total_alerts': len(price_monitor.alerts),
        'min_price': float(df['current_price'].min()) if 'current_price' in df.columns else 0,
        'max_price': float(df['current_price'].max()) if 'current_price' in df.columns else 0
    }

    # Get list of existing charts
    chart_files = []
    if os.path.exists('static/charts'):
        chart_files = [f for f in os.listdir('static/charts') if f.endswith('.png')]

    return render_template('index.html', stats=stats, chart_files=chart_files)


# ==================== MONITORING ROUTES ====================

@app.route('/monitoring')
def monitoring_page():
    alerts = price_monitor.get_alerts(10)
    monitored_products = price_monitor.monitored_products

    return render_template('monitoring.html',
                           monitored_products=monitored_products,
                           alerts=alerts,
                           total_alerts=len(price_monitor.alerts))


@app.route('/api/monitor/add', methods=['POST'])
def add_to_monitor():
    data = request.json
    product_id = data.get('product_id', '').strip()
    platform = data.get('platform', '').strip()
    target_price = data.get('target_price')

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
    platform = data.get('platform')

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
    sample_products = df.head(5).to_dict('records')
    categories = df['category'].unique().tolist() if 'category' in df.columns else []

    return render_template('recommendations.html',
                           sample_products=sample_products,
                           categories=categories,
                           ml_available=ML_AVAILABLE)


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

@app.route('/products')
def products():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    platform = request.args.get('platform', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')

    filtered_df = df.copy()

    if search:
        filtered_df = filtered_df[filtered_df['name'].str.contains(search, case=False, na=False)]

    if platform:
        filtered_df = filtered_df[filtered_df['platform'] == platform]

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

    platforms = df['platform'].unique().tolist() if 'platform' in df.columns else []

    return render_template('products.html',
                           products=products_data,
                           page=page,
                           total_pages=total_pages,
                           total=total,
                           search=search,
                           selected_platform=platform,
                           min_price=min_price,
                           max_price=max_price,
                           platforms=platforms)


@app.route('/analysis')
def analysis():
    # Calculate analysis statistics
    stats = {
        'price': {
            'mean': float(df['current_price'].mean()) if 'current_price' in df.columns else 0,
            'median': float(df['current_price'].median()) if 'current_price' in df.columns else 0,
            'min': float(df['current_price'].min()) if 'current_price' in df.columns else 0,
            'max': float(df['current_price'].max()) if 'current_price' in df.columns else 0,
            'std': float(df['current_price'].std()) if 'current_price' in df.columns else 0
        },
        'rating': {
            'mean': float(df['rating'].mean()) if 'rating' in df.columns else 0,
            'count_above_4': int((df['rating'] > 4).sum()) if 'rating' in df.columns else 0,
            'count_below_3': int((df['rating'] < 3).sum()) if 'rating' in df.columns else 0
        },
        'platform_stats': {},
        'category_stats': {}
    }

    # Platform statistics
    if 'platform' in df.columns:
        for platform in df['platform'].unique():
            platform_df = df[df['platform'] == platform]
            stats['platform_stats'][platform] = {
                'count': len(platform_df),
                'avg_price': float(
                    platform_df['current_price'].mean()) if 'current_price' in platform_df.columns else 0,
                'avg_rating': float(platform_df['rating'].mean()) if 'rating' in platform_df.columns else 0
            }

    # Category statistics
    if 'category' in df.columns:
        top_categories = df['category'].value_counts().head(5)
        for category, count in top_categories.items():
            category_df = df[df['category'] == category]
            stats['category_stats'][category] = {
                'count': int(count),
                'avg_price': float(category_df['current_price'].mean()) if 'current_price' in category_df.columns else 0
            }

    # Get list of all charts
    chart_files = []
    if os.path.exists('static/charts'):
        chart_files = sorted([f for f in os.listdir('static/charts') if f.endswith('.png')])

    return render_template('analysis.html',
                           chart_files=chart_files,
                           stats=stats,
                           total_products=len(df))


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
        platform_dist = df['platform'].value_counts().to_dict()
        summary['platform_distribution'] = platform_dist

    return render_template('database.html', summary=summary)


@app.route('/generate_all_charts')
def generate_all_charts():
    try:
        charts = []

        price_chart = generate_price_chart()
        if price_chart:
            charts.append({'name': 'Price Distribution', 'file': price_chart})

        rating_chart = generate_rating_chart()
        if rating_chart:
            charts.append({'name': 'Rating Distribution', 'file': rating_chart})

        category_chart = generate_category_chart()
        if category_chart:
            charts.append({'name': 'Category Distribution', 'file': category_chart})

        return jsonify({
            'success': True,
            'message': f'Generated {len(charts)} charts',
            'charts': charts
        })

    except Exception as e:
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
    print("\nPress Ctrl+C to stop")
    print("=" * 60)

    app.run(debug=True, host='127.0.0.1', port=5000)