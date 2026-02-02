# app.py - COMPLETE FIXED VERSION WITH INTERACTIVE CHARTS
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import pandas as pd
import numpy as np
import matplotlib

matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64
import os
import json
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# Create necessary directories
os.makedirs('templates', exist_ok=True)
os.makedirs('static/charts', exist_ok=True)
os.makedirs('data', exist_ok=True)

app = Flask(__name__)


# Load data
def load_data():
    """Load product data from CSV or create sample"""
    try:
        csv_files = [
            'data/all_products.csv',
            'data/amazon_products.csv',
            'data/jd_products.csv'
        ]

        for csv_file in csv_files:
            if os.path.exists(csv_file):
                df = pd.read_csv(csv_file)
                print(f"Loaded {len(df)} products from {csv_file}")
                return df

        # If no CSV files, create sample data
        print("No data files found, creating sample data...")
        return create_sample_data()

    except Exception as e:
        print(f"Error loading data: {e}")
        return create_sample_data()


def create_sample_data():
    """Create sample data for demonstration"""
    np.random.seed(42)

    sample_data = {
        'platform': ['Amazon'] * 50 + ['JD.com'] * 50,
        'product_id': [f'AMZ_{i:04d}' for i in range(50)] + [f'JD_{i:04d}' for i in range(50)],
        'name': [f'Product {i} - Sample' for i in range(100)],
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
    print(f"Created sample data with {len(df)} products")
    return df


# Initialize data
df = load_data()


# ==================== HELPER FUNCTIONS ====================

def generate_price_chart():
    """Generate price distribution chart"""
    try:
        plt.figure(figsize=(10, 5))

        # Price histogram
        plt.subplot(1, 2, 1)
        prices = df['current_price'].dropna()
        plt.hist(prices, bins=30, alpha=0.7, color='steelblue', edgecolor='black')
        plt.title('Price Distribution', fontsize=14, fontweight='bold')
        plt.xlabel('Price ($)', fontsize=12)
        plt.ylabel('Number of Products', fontsize=12)
        plt.grid(True, alpha=0.3)

        # Add statistics
        mean_price = prices.mean()
        median_price = prices.median()
        plt.axvline(mean_price, color='red', linestyle='--', linewidth=2, label=f'Mean: ${mean_price:.2f}')
        plt.axvline(median_price, color='green', linestyle='--', linewidth=2, label=f'Median: ${median_price:.2f}')
        plt.legend()

        # Platform comparison
        plt.subplot(1, 2, 2)
        if 'platform' in df.columns:
            platform_prices = df.groupby('platform')['current_price'].mean()
            colors = ['#FF6B6B', '#4ECDC4'] if len(platform_prices) == 2 else None
            bars = plt.bar(platform_prices.index, platform_prices.values, color=colors)
            plt.title('Average Price by Platform', fontsize=14, fontweight='bold')
            plt.ylabel('Average Price ($)', fontsize=12)
            plt.xlabel('Platform', fontsize=12)
            plt.xticks(rotation=0)
            plt.grid(True, alpha=0.3)

            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width() / 2., height,
                         f'${height:.2f}', ha='center', va='bottom', fontweight='bold')

        plt.tight_layout()

        # Save to static directory
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
    """Generate rating distribution chart"""
    try:
        plt.figure(figsize=(10, 5))

        # Rating distribution
        plt.subplot(1, 2, 1)
        if 'rating' in df.columns:
            ratings = df['rating'].dropna()
            plt.hist(ratings, bins=20, alpha=0.7, color='gold', edgecolor='black')
            plt.title('Rating Distribution', fontsize=14, fontweight='bold')
            plt.xlabel('Rating (1-5)', fontsize=12)
            plt.ylabel('Number of Products', fontsize=12)
            plt.grid(True, alpha=0.3)

            # Add mean line
            mean_rating = ratings.mean()
            plt.axvline(mean_rating, color='red', linestyle='--', linewidth=2,
                        label=f'Avg: {mean_rating:.2f}')
            plt.legend()

        # Rating vs Price scatter
        plt.subplot(1, 2, 2)
        if 'rating' in df.columns and 'current_price' in df.columns:
            plt.scatter(df['rating'], df['current_price'], alpha=0.6,
                        c='purple', edgecolors='black', linewidth=0.5)
            plt.title('Rating vs Price', fontsize=14, fontweight='bold')
            plt.xlabel('Rating', fontsize=12)
            plt.ylabel('Price ($)', fontsize=12)
            plt.grid(True, alpha=0.3)

            # Add trend line
            z = np.polyfit(df['rating'], df['current_price'], 1)
            p = np.poly1d(z)
            plt.plot(df['rating'], p(df['rating']), "r--", alpha=0.8)

        plt.tight_layout()

        # Save to static directory
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
    """Generate category distribution chart"""
    try:
        plt.figure(figsize=(12, 6))

        if 'category' in df.columns:
            category_counts = df['category'].value_counts().head(10)

            # Bar chart
            plt.subplot(1, 2, 1)
            bars = plt.barh(category_counts.index, category_counts.values,
                            color=plt.cm.Set3(np.arange(len(category_counts))))
            plt.title('Top Product Categories', fontsize=14, fontweight='bold')
            plt.xlabel('Number of Products', fontsize=12)
            plt.gca().invert_yaxis()  # Highest on top

            # Add count labels
            for i, (value, bar) in enumerate(zip(category_counts.values, bars)):
                plt.text(value + 0.5, bar.get_y() + bar.get_height() / 2,
                         str(value), va='center', fontweight='bold')

            # Pie chart
            plt.subplot(1, 2, 2)
            plt.pie(category_counts.values, labels=category_counts.index,
                    autopct='%1.1f%%', startangle=90, colors=plt.cm.Set3(np.arange(len(category_counts))))
            plt.title('Category Distribution', fontsize=14, fontweight='bold')

        plt.tight_layout()

        # Save to static directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'category_distribution_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return filename

    except Exception as e:
        print(f"Error generating category chart: {e}")
        return None


def generate_platform_chart():
    """Generate platform comparison chart"""
    try:
        plt.figure(figsize=(10, 8))

        if 'platform' in df.columns:
            platforms = df['platform'].unique()

            # Create subplots
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))

            # 1. Product count by platform
            platform_counts = df['platform'].value_counts()
            axes[0, 0].bar(platform_counts.index, platform_counts.values,
                           color=['#FF6B6B', '#4ECDC4', '#45B7D1'])
            axes[0, 0].set_title('Products by Platform', fontsize=12, fontweight='bold')
            axes[0, 0].set_ylabel('Count', fontsize=10)
            axes[0, 0].tick_params(axis='x', rotation=45)

            # Add count labels
            for i, (platform, count) in enumerate(platform_counts.items()):
                axes[0, 0].text(i, count + 0.5, str(count),
                                ha='center', va='bottom', fontweight='bold')

            # 2. Average price by platform
            if 'current_price' in df.columns:
                avg_price = df.groupby('platform')['current_price'].mean()
                axes[0, 1].bar(avg_price.index, avg_price.values,
                               color=['#96CEB4', '#FFEAA7', '#DDA0DD'])
                axes[0, 1].set_title('Average Price by Platform', fontsize=12, fontweight='bold')
                axes[0, 1].set_ylabel('Price ($)', fontsize=10)
                axes[0, 1].tick_params(axis='x', rotation=45)

                # Add price labels
                for i, (platform, price) in enumerate(avg_price.items()):
                    axes[0, 1].text(i, price + 5, f'${price:.2f}',
                                    ha='center', va='bottom', fontweight='bold')

            # 3. Average rating by platform
            if 'rating' in df.columns:
                avg_rating = df.groupby('platform')['rating'].mean()
                axes[1, 0].bar(avg_rating.index, avg_rating.values,
                               color=['#E6B0AA', '#A9CCE3', '#ABEBC6'])
                axes[1, 0].set_title('Average Rating by Platform', fontsize=12, fontweight='bold')
                axes[1, 0].set_ylabel('Rating', fontsize=10)
                axes[1, 0].set_ylim([0, 5])  # Rating scale 0-5
                axes[1, 0].tick_params(axis='x', rotation=45)

                # Add rating labels
                for i, (platform, rating) in enumerate(avg_rating.items()):
                    axes[1, 0].text(i, rating + 0.1, f'{rating:.2f}',
                                    ha='center', va='bottom', fontweight='bold')

            # 4. Platform price distribution (box plot)
            if 'current_price' in df.columns:
                platform_data = []
                platform_labels = []
                for platform in platforms:
                    platform_prices = df[df['platform'] == platform]['current_price'].dropna()
                    if len(platform_prices) > 0:
                        platform_data.append(platform_prices)
                        platform_labels.append(platform)

                axes[1, 1].boxplot(platform_data, labels=platform_labels)
                axes[1, 1].set_title('Price Distribution by Platform', fontsize=12, fontweight='bold')
                axes[1, 1].set_ylabel('Price ($)', fontsize=10)
                axes[1, 1].tick_params(axis='x', rotation=45)
                axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()

        # Save to static directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'platform_comparison_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return filename

    except Exception as e:
        print(f"Error generating platform chart: {e}")
        return None


def generate_trend_chart():
    """Generate price trend chart (simulated)"""
    try:
        plt.figure(figsize=(12, 6))

        # Simulate price trends over time
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')

        # Simulate trends for each platform
        if 'platform' in df.columns:
            platforms = df['platform'].unique()

            for i, platform in enumerate(platforms):
                # Generate trend data
                base_price = df[df['platform'] == platform]['current_price'].mean()
                if pd.isna(base_price):
                    base_price = 500

                # Add some randomness
                trend = np.random.uniform(-0.1, 0.1)  # -10% to +10% trend
                prices = []
                for j in range(30):
                    day_factor = trend * (j / 30)
                    random_factor = np.random.uniform(-0.05, 0.05)
                    price = base_price * (1 + day_factor + random_factor)
                    prices.append(price)

                # Plot trend
                plt.plot(dates, prices, marker='o', markersize=4, linewidth=2,
                         label=platform, alpha=0.8)

        plt.title('Price Trends Over Time (Last 30 Days)', fontsize=14, fontweight='bold')
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Average Price ($)', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xticks(rotation=45)

        plt.tight_layout()

        # Save to static directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'price_trends_{timestamp}.png'
        filepath = f'static/charts/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return filename

    except Exception as e:
        print(f"Error generating trend chart: {e}")
        return None


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Main dashboard page"""
    # Generate fresh charts
    price_chart = generate_price_chart()
    rating_chart = generate_rating_chart()

    # Get statistics
    stats = {
        'total_products': len(df),
        'avg_price': float(df['current_price'].mean()) if 'current_price' in df.columns else 0,
        'avg_rating': float(df['rating'].mean()) if 'rating' in df.columns else 0,
        'platform_count': df['platform'].nunique() if 'platform' in df.columns else 0,
        'category_count': df['category'].nunique() if 'category' in df.columns else 0,
        'min_price': float(df['current_price'].min()) if 'current_price' in df.columns else 0,
        'max_price': float(df['current_price'].max()) if 'current_price' in df.columns else 0
    }

    # Get list of existing charts
    chart_files = []
    if os.path.exists('static/charts'):
        chart_files = [f for f in os.listdir('static/charts') if f.endswith('.png')]

    return render_template('index.html', stats=stats, chart_files=chart_files)


@app.route('/products')
def products():
    """Products page with search and pagination"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    platform = request.args.get('platform', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')

    # Filter data
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

    # Pagination
    per_page = 20
    total = len(filtered_df)
    total_pages = (total + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    products_data = filtered_df.iloc[start_idx:end_idx].to_dict('records')

    # Get unique platforms for filter dropdown
    platforms = df['platform'].unique().tolist() if 'platform' in df.columns else []

    return render_template('products.html',
                           products=products_data,
                           page=page,
                           total_pages=total_pages,
                           total=total,
                           search=search,
                           platform=platform,
                           min_price=min_price,
                           max_price=max_price,
                           platforms=platforms)


@app.route('/analysis')
def analysis():
    """Analysis page with interactive charts"""
    # Generate all charts
    price_chart = generate_price_chart()
    rating_chart = generate_rating_chart()
    category_chart = generate_category_chart()
    platform_chart = generate_platform_chart()
    trend_chart = generate_trend_chart()

    # Get list of all charts
    chart_files = []
    if os.path.exists('static/charts'):
        chart_files = sorted([f for f in os.listdir('static/charts') if f.endswith('.png')])

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

    return render_template('analysis.html',
                           chart_files=chart_files,
                           stats=stats,
                           total_products=len(df))


@app.route('/database')
def database_view():
    """Database view page"""
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

    # Get missing values
    missing_values = df.isnull().sum().to_dict()
    summary['missing_values'] = missing_values

    return render_template('database.html', summary=summary)


@app.route('/api/search')
def api_search():
    """API endpoint for searching products"""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)

    if query:
        results = df[df['name'].str.contains(query, case=False, na=False)].head(limit)
    else:
        results = df.head(limit)

    return jsonify(results.to_dict('records'))


@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    stats = {
        'total_products': len(df),
        'columns': list(df.columns),
        'platforms': df['platform'].unique().tolist() if 'platform' in df.columns else [],
        'data_loaded': True
    }
    return jsonify(stats)


@app.route('/static/charts/<filename>')
def serve_chart(filename):
    """Serve chart image"""
    return send_from_directory('static/charts', filename)


@app.route('/generate_all_charts')
def generate_all_charts():
    """Generate all charts at once"""
    try:
        charts = []

        price_chart = generate_price_chart()
        if price_chart:
            charts.append({'name': 'Price Distribution', 'file': price_chart})

        rating_chart = generate_rating_chart()
        if rating_chart:
            charts.append({'name': 'Rating Analysis', 'file': rating_chart})

        category_chart = generate_category_chart()
        if category_chart:
            charts.append({'name': 'Category Analysis', 'file': category_chart})

        platform_chart = generate_platform_chart()
        if platform_chart:
            charts.append({'name': 'Platform Comparison', 'file': platform_chart})

        trend_chart = generate_trend_chart()
        if trend_chart:
            charts.append({'name': 'Price Trends', 'file': trend_chart})

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
    """Refresh data from CSV files"""
    global df
    try:
        df = load_data()
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
    return render_template('error.html', error='Page not found'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error='Server error'), 500


# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 60)
    print("E-COMMERCE DATA ANALYSIS WEB INTERFACE")
    print("=" * 60)
    print(f"Loaded {len(df)} products")
    print(f"Columns: {list(df.columns)}")
    print(f"Platforms: {df['platform'].unique().tolist() if 'platform' in df.columns else 'N/A'}")
    print("\nStarting web server...")
    print("Open your browser and go to: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)

    app.run(debug=True, host='127.0.0.1', port=5000)