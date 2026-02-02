# ml/product_similarity.py
import numpy as np
from typing import List, Dict
from sklearn.preprocessing import StandardScaler


class AdvancedSimilarity:
    """Advanced product similarity calculations"""

    @staticmethod
    def calculate_weighted_similarity(product1: Dict, product2: Dict,
                                      weights: Dict = None) -> float:
        """
        Calculate weighted similarity between two products
        Weights different features differently
        """
        if weights is None:
            weights = {
                'name': 0.4,
                'category': 0.3,
                'price': 0.2,
                'rating': 0.1
            }

        similarity_score = 0
        total_weight = 0

        # Name similarity (simple string matching)
        if 'name' in product1 and 'name' in product2:
            name_sim = AdvancedSimilarity._text_similarity(
                product1['name'], product2['name']
            )
            similarity_score += name_sim * weights['name']
            total_weight += weights['name']

        # Category similarity
        if 'category' in product1 and 'category' in product2:
            category_sim = 1.0 if product1['category'] == product2['category'] else 0.0
            similarity_score += category_sim * weights['category']
            total_weight += weights['category']

        # Price similarity (normalized)
        if 'current_price' in product1 and 'current_price' in product2:
            price_diff = abs(product1['current_price'] - product2['current_price'])
            # Normalize: assume max price difference of 5000
            price_sim = max(0, 1 - (price_diff / 5000))
            similarity_score += price_sim * weights['price']
            total_weight += weights['price']

        # Rating similarity
        if 'rating' in product1 and 'rating' in product2:
            rating_diff = abs(product1['rating'] - product2['rating'])
            rating_sim = max(0, 1 - (rating_diff / 5))  # Ratings out of 5
            similarity_score += rating_sim * weights['rating']
            total_weight += weights['rating']

        # Normalize by total weight used
        if total_weight > 0:
            return similarity_score / total_weight
        return 0.0

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """Simple text similarity using word overlap"""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def find_similar_products(target_product: Dict, all_products: List[Dict],
                              n_results: int = 5) -> List[Dict]:
        """Find similar products using advanced similarity"""
        similarities = []

        for product in all_products:
            if product['product_id'] == target_product['product_id']:
                continue

            similarity = AdvancedSimilarity.calculate_weighted_similarity(
                target_product, product
            )

            similarities.append({
                'product': product,
                'similarity': similarity
            })

        # Sort by similarity
        similarities.sort(key=lambda x: x['similarity'], reverse=True)

        # Return top results
        return [
            {
                **item['product'],
                'advanced_similarity': item['similarity']
            }
            for item in similarities[:n_results]
        ]