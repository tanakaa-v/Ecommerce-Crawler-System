# ml/recommender.py
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pickle


class ProductRecommender:
    """
    Machine Learning Recommendation System
    Uses content-based filtering for product recommendations
    """

    def __init__(self, db_connection=None):
        self.db = db_connection
        self.products_df = None
        self.vectorizer = None
        self.feature_matrix = None
        self.similarity_matrix = None

        print("=" * 60)
        print("🤖 ML RECOMMENDATION SYSTEM")
        print("=" * 60)

    def load_products(self, products_data: List[Dict]):
        """Load products data for training"""
        if not products_data:
            print("❌ No products data provided")
            return False

        # Convert to DataFrame
        self.products_df = pd.DataFrame(products_data)

        # Prepare features for ML
        self._prepare_features()

        print(f"✅ Loaded {len(self.products_df)} products for recommendation")
        return True

    def _prepare_features(self):
        """Prepare features for similarity calculation"""
        # Combine text features for content-based filtering
        self.products_df['combined_features'] = (
                self.products_df['name'].fillna('') + ' ' +
                self.products_df['category'].fillna('') + ' ' +
                self.products_df['store_name'].fillna('')
        )

        # Create TF-IDF vectors
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=1000  # Limit features for performance
        )

        self.feature_matrix = self.vectorizer.fit_transform(
            self.products_df['combined_features']
        )

        # Calculate similarity matrix
        self.similarity_matrix = cosine_similarity(self.feature_matrix)

        print(f"✅ Prepared features: {self.feature_matrix.shape[1]} dimensions")

    def recommend_similar_products(self, product_id: str, n_recommendations: int = 5) -> List[Dict]:
        """Recommend similar products based on content"""
        if self.products_df is None or self.similarity_matrix is None:
            print("❌ Model not trained yet")
            return []

        # Find product index
        if product_id not in self.products_df['product_id'].values:
            print(f"❌ Product {product_id} not found in dataset")
            return []

        product_idx = self.products_df[self.products_df['product_id'] == product_id].index[0]

        # Get similarity scores
        similarity_scores = list(enumerate(self.similarity_matrix[product_idx]))

        # Sort by similarity (excluding the product itself)
        similarity_scores = sorted(similarity_scores, key=lambda x: x[1], reverse=True)[1:]

        # Get top N recommendations
        recommendations = []
        for idx, score in similarity_scores[:n_recommendations]:
            product = self.products_df.iloc[idx].to_dict()
            product['similarity_score'] = float(score)
            recommendations.append(product)

        return recommendations

    def recommend_by_user_preferences(self, liked_products: List[str],
                                      disliked_products: List[str] = None,
                                      n_recommendations: int = 10) -> List[Dict]:
        """
        Recommend products based on user likes/dislikes
        Simple collaborative filtering approach
        """
        if self.products_df is None or self.similarity_matrix is None:
            print("❌ Model not trained yet")
            return []

        if not liked_products:
            print("❌ No liked products provided")
            return []

        # Calculate average similarity to liked products
        user_profile = np.zeros(self.similarity_matrix.shape[0])

        for product_id in liked_products:
            if product_id in self.products_df['product_id'].values:
                idx = self.products_df[self.products_df['product_id'] == product_id].index[0]
                user_profile += self.similarity_matrix[idx]

        # Subtract similarity to disliked products
        if disliked_products:
            for product_id in disliked_products:
                if product_id in self.products_df['product_id'].values:
                    idx = self.products_df[self.products_df['product_id'] == product_id].index[0]
                    user_profile -= self.similarity_matrix[idx] * 0.5  # Penalty factor

        # Normalize by number of liked products
        if len(liked_products) > 0:
            user_profile /= len(liked_products)

        # Get top recommendations (excluding liked products)
        recommendation_indices = user_profile.argsort()[::-1]

        recommendations = []
        for idx in recommendation_indices:
            product_id = self.products_df.iloc[idx]['product_id']

            # Skip already liked/disliked products
            if product_id in liked_products or (disliked_products and product_id in disliked_products):
                continue

            product = self.products_df.iloc[idx].to_dict()
            product['preference_score'] = float(user_profile[idx])
            recommendations.append(product)

            if len(recommendations) >= n_recommendations:
                break

        return recommendations

    def recommend_by_price_range(self, min_price: float, max_price: float,
                                 preferred_categories: List[str] = None,
                                 n_recommendations: int = 10) -> List[Dict]:
        """Recommend products within price range"""
        if self.products_df is None:
            print("❌ No products loaded")
            return []

        # Filter by price
        filtered_df = self.products_df[
            (self.products_df['current_price'] >= min_price) &
            (self.products_df['current_price'] <= max_price)
            ].copy()

        # Filter by category if specified
        if preferred_categories:
            filtered_df = filtered_df[
                filtered_df['category'].isin(preferred_categories)
            ]

        if filtered_df.empty:
            print("❌ No products match the criteria")
            return []

        # Sort by rating (or other criteria)
        filtered_df = filtered_df.sort_values(
            by=['rating', 'review_count'],
            ascending=[False, False]
        )

        # Return top recommendations
        recommendations = filtered_df.head(n_recommendations).to_dict('records')

        return recommendations

    def train_simple_classifier(self, target_column: str = 'category'):
        """
        Train a simple classifier to predict product category
        This is a basic ML demonstration
        """
        from sklearn.model_selection import train_test_split
        from sklearn.naive_bayes import MultinomialNB
        from sklearn.metrics import accuracy_score

        if self.products_df is None or self.feature_matrix is None:
            print("❌ No data to train on")
            return None

        # Prepare data
        X = self.feature_matrix
        y = self.products_df[target_column].fillna('Unknown')

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Train classifier
        classifier = MultinomialNB()
        classifier.fit(X_train, y_train)

        # Evaluate
        y_pred = classifier.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        print(f"✅ Trained {target_column} classifier")
        print(f"   Accuracy: {accuracy:.2%}")
        print(f"   Classes: {len(classifier.classes_)}")

        return classifier

    def save_model(self, filename: str = 'ml/recommender_model.pkl'):
        """Save trained model to file"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            model_data = {
                'vectorizer': self.vectorizer,
                'similarity_matrix': self.similarity_matrix,
                'products_df': self.products_df
            }

            with open(filename, 'wb') as f:
                pickle.dump(model_data, f)

            print(f"✅ Model saved to {filename}")
            return True

        except Exception as e:
            print(f"❌ Failed to save model: {e}")
            return False

    def load_model(self, filename: str = 'ml/recommender_model.pkl'):
        """Load trained model from file"""
        try:
            with open(filename, 'rb') as f:
                model_data = pickle.load(f)

            self.vectorizer = model_data['vectorizer']
            self.similarity_matrix = model_data['similarity_matrix']
            self.products_df = model_data['products_df']

            print(f"✅ Model loaded from {filename}")
            print(f"   Products: {len(self.products_df)}")
            return True

        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            return False

    def get_recommendation_stats(self) -> Dict:
        """Get recommendation system statistics"""
        if self.products_df is None:
            return {}

        return {
            'total_products': len(self.products_df),
            'categories': self.products_df['category'].nunique(),
            'platforms': self.products_df['platform'].nunique(),
            'price_range': {
                'min': self.products_df['current_price'].min(),
                'max': self.products_df['current_price'].max(),
                'avg': self.products_df['current_price'].mean()
            }
        }


def demo_recommendation():
    """Demonstrate the recommendation system"""
    print("\n🤖 DEMONSTRATING ML RECOMMENDATION SYSTEM")
    print("-" * 50)

    # Create sample data
    sample_products = [
        {
            'product_id': 'AMZ_001',
            'name': 'Apple MacBook Pro 16 inch',
            'category': 'Laptop',
            'current_price': 2499.99,
            'rating': 4.8,
            'store_name': 'Apple Store',
            'platform': 'Amazon'
        },
        {
            'product_id': 'AMZ_002',
            'name': 'Dell XPS 15 Laptop',
            'category': 'Laptop',
            'current_price': 1899.99,
            'rating': 4.6,
            'store_name': 'Dell Store',
            'platform': 'Amazon'
        },
        {
            'product_id': 'AMZ_003',
            'name': 'iPhone 15 Pro Max',
            'category': 'Phone',
            'current_price': 1199.99,
            'rating': 4.7,
            'store_name': 'Apple Store',
            'platform': 'Amazon'
        },
        {
            'product_id': 'JD_001',
            'name': '华为MateBook X Pro',
            'category': 'Laptop',
            'current_price': 1599.99,
            'rating': 4.5,
            'store_name': '华为官方',
            'platform': 'JD.com'
        }
    ]

    # Initialize recommender
    recommender = ProductRecommender()
    recommender.load_products(sample_products)

    # Test similar products recommendation
    print("\n1. SIMILAR PRODUCTS RECOMMENDATION:")
    similar = recommender.recommend_similar_products('AMZ_001', 2)
    for i, product in enumerate(similar, 1):
        print(f"   {i}. {product['name']} (Score: {product['similarity_score']:.3f})")

    # Test user preference recommendation
    print("\n2. USER PREFERENCE RECOMMENDATION:")
    user_likes = ['AMZ_001', 'AMZ_003']  # User likes Apple products
    user_recommendations = recommender.recommend_by_user_preferences(user_likes, n_recommendations=2)
    for i, product in enumerate(user_recommendations, 1):
        print(f"   {i}. {product['name']} (Score: {product['preference_score']:.3f})")

    # Test price range recommendation
    print("\n3. PRICE RANGE RECOMMENDATION ($1000-$2000):")
    price_recs = recommender.recommend_by_price_range(1000, 2000, n_recommendations=2)
    for i, product in enumerate(price_recs, 1):
        print(f"   {i}. {product['name']} - ${product['current_price']:.2f}")

    # Show stats
    stats = recommender.get_recommendation_stats()
    print(f"\n📊 Recommendation System Stats:")
    print(f"   Products: {stats['total_products']}")
    print(f"   Categories: {stats['categories']}")
    print(f"   Price range: ${stats['price_range']['min']:.2f} - ${stats['price_range']['max']:.2f}")

    print("\n✅ ML Recommendation System Demo Complete!")


if __name__ == "__main__":
    demo_recommendation()