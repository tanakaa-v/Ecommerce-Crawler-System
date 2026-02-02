#MySQL Database Module
import mysql.connector
import pandas as pd
import json
from datetime import datetime
import os
from typing import List, Dict, Optional
import sys


class MySQLDatabase:
    """MySQL Database Manager for E-commerce Data"""

    def __init__(self, host='localhost', user='root', password='', database='ecommerce_db'):
        """
        Initialize MySQL database connection
        Default credentials - user should update these
        """
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database
        }

        self.connection = None
        self.cursor = None

        print("=" * 60)
        print("🗄️  MYSQL DATABASE MODULE")
        print("=" * 60)

    def _clean_product_data(self, product: Dict, platform: str = None) -> Dict:
        """Clean and standardize product data before insertion"""
        import pandas as pd
        import json

        cleaned = product.copy()

        # 1. Set platform if provided
        if platform and ('platform' not in cleaned or pd.isna(cleaned.get('platform'))):
            cleaned['platform'] = platform

        # 2. Ensure product_id exists
        if 'product_id' not in cleaned or pd.isna(cleaned.get('product_id')):
            cleaned['product_id'] = f"UNKNOWN_{hash(str(product)) % 10000}"

        # 3. Ensure name exists
        if 'name' not in cleaned or pd.isna(cleaned.get('name')):
            cleaned['name'] = f"Product {cleaned['product_id']}"

        # 4. Fix numeric fields (handle NaN/None)
        numeric_fields = ['current_price', 'original_price', 'rating', 'review_count']
        for field in numeric_fields:
            if field in cleaned:
                if pd.isna(cleaned[field]) or cleaned[field] is None:
                    if field == 'review_count':
                        cleaned[field] = 0
                    else:
                        cleaned[field] = 0.0
                elif isinstance(cleaned[field], str):
                    # Convert string to number
                    try:
                        # Remove currency symbols and commas
                        value_str = str(cleaned[field]).replace('¥', '').replace('$', '').replace(',', '').strip()
                        if field == 'review_count':
                            cleaned[field] = int(float(value_str)) if value_str else 0
                        else:
                            cleaned[field] = float(value_str) if value_str else 0.0
                    except:
                        cleaned[field] = 0.0 if field != 'review_count' else 0

        # 5. Fix text fields (handle NaN)
        text_fields = ['store_name', 'category', 'image_url']
        for field in text_fields:
            if field in cleaned and (pd.isna(cleaned[field]) or cleaned[field] is None):
                cleaned[field] = ''

        # 6. Fix details JSON field
        if 'details' in cleaned:
            if pd.isna(cleaned['details']) or cleaned['details'] is None:
                cleaned['details'] = '{}'
            elif isinstance(cleaned['details'], str):
                # Try to validate JSON
                try:
                    json.loads(cleaned['details'])
                except json.JSONDecodeError:
                    # If invalid JSON, wrap it
                    cleaned['details'] = json.dumps({'raw_details': cleaned['details'][:200]})
            else:
                # Convert non-string to JSON
                try:
                    cleaned['details'] = json.dumps(cleaned['details'])
                except:
                    cleaned['details'] = json.dumps({'data': str(cleaned['details'])[:200]})

        # 7. Fix crawled_at timestamp
        if 'crawled_at' not in cleaned or pd.isna(cleaned.get('crawled_at')):
            from datetime import datetime
            cleaned['crawled_at'] = datetime.now()

        # 8. Trim string lengths to fit database columns
        if len(str(cleaned.get('name', ''))) > 500:
            cleaned['name'] = str(cleaned['name'])[:497] + '...'

        if len(str(cleaned.get('store_name', ''))) > 200:
            cleaned['store_name'] = str(cleaned['store_name'])[:197] + '...'

        return cleaned
    def connect(self):
        """Establish connection to MySQL database"""
        try:
            self.connection = mysql.connector.connect(**self.config)
            self.cursor = self.connection.cursor()
            print("✅ Connected to MySQL database")
            return True
        except mysql.connector.Error as err:
            print(f"❌ MySQL Connection Error: {err}")

            # Try to create database if it doesn't exist
            if err.errno == 1049:  # Database doesn't exist
                print("⚠️ Database not found, attempting to create...")
                return self._create_database()
            elif err.errno == 1045:  # Access denied
                print("\n🔑 MySQL Access Denied!")
                print("Please update database credentials in database.py")
                print("Or create database with:")
                print("  CREATE DATABASE ecommerce_db;")
                print("  CREATE USER 'crawler'@'localhost' IDENTIFIED BY 'password';")
                print("  GRANT ALL ON ecommerce_db.* TO 'crawler'@'localhost';")

            return False

    def _create_database(self):
        """Create database if it doesn't exist"""
        try:
            # Connect without database
            temp_config = self.config.copy()
            temp_config.pop('database')
            temp_conn = mysql.connector.connect(**temp_config)
            temp_cursor = temp_conn.cursor()

            # Create database
            temp_cursor.execute(f"CREATE DATABASE {self.config['database']}")
            print(f"✅ Created database: {self.config['database']}")

            temp_cursor.close()
            temp_conn.close()

            # Now connect to the new database
            return self.connect()

        except mysql.connector.Error as err:
            print(f"❌ Failed to create database: {err}")
            return False

    def create_tables(self):
        """Create all necessary tables with proper structure"""
        if not self.connection:
            print("❌ Not connected to database")
            return False

        try:
            # Products table (main table)
            products_table = """
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                platform VARCHAR(20) NOT NULL,
                product_id VARCHAR(100) NOT NULL,
                name VARCHAR(500) NOT NULL,
                current_price DECIMAL(10, 2),
                original_price DECIMAL(10, 2),
                rating DECIMAL(3, 2),
                review_count INT,
                store_name VARCHAR(200),
                category VARCHAR(100),
                details JSON,
                image_url VARCHAR(500),
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_product (platform, product_id),
                INDEX idx_platform (platform),
                INDEX idx_price (current_price),
                INDEX idx_category (category),
                INDEX idx_store (store_name)
            )
            """

            # Price history table for trend analysis
            price_history_table = """
            CREATE TABLE IF NOT EXISTS price_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                INDEX idx_product_price (product_id, recorded_at),
                INDEX idx_recorded_at (recorded_at)
            )
            """

            # Brands statistics table
            brands_table = """
            CREATE TABLE IF NOT EXISTS brand_stats (
                id INT AUTO_INCREMENT PRIMARY KEY,
                platform VARCHAR(20),
                brand_name VARCHAR(100),
                product_count INT DEFAULT 0,
                avg_price DECIMAL(10, 2),
                avg_rating DECIMAL(3, 2),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_brand (platform, brand_name)
            )
            """

            # Execute table creation
            self.cursor.execute(products_table)
            self.cursor.execute(price_history_table)
            self.cursor.execute(brands_table)

            self.connection.commit()
            print("✅ Created database tables:")
            print("   - products (main products table)")
            print("   - price_history (price trends)")
            print("   - brand_stats (brand analytics)")

            return True

        except mysql.connector.Error as err:
            print(f"❌ Table creation error: {err}")
            return False

    def insert_or_update_product(self, product: Dict) -> bool:
        """
        Insert or update product with deduplication
        Uses ON DUPLICATE KEY UPDATE for incremental updates
        """
        if not self.connection:
            print("❌ Not connected to database")
            return False

        try:
            # 1. Clean the product data first
            product = self._clean_product_data(product)

            # 2. Prepare details JSON (SAFER)
            details_value = product.get('details', {})
            details_json = '{}'

            if isinstance(details_value, str):
                try:
                    # Try to parse existing JSON
                    json.loads(details_value)
                    details_json = details_value
                except json.JSONDecodeError:
                    # If invalid, create simple JSON
                    details_json = json.dumps({'raw_data': details_value[:200]}, ensure_ascii=False)
            else:
                # Convert to JSON string
                try:
                    details_json = json.dumps(details_value, ensure_ascii=False)
                except:
                    details_json = json.dumps({'data': str(details_value)[:200]}, ensure_ascii=False)

            # 3. Prepare category safely
            category = str(product.get('category', '')).strip()[:100]
            if not category:
                category = 'General'

            # 4. Prepare all other values with safety checks
            platform = str(product.get('platform', 'Unknown')).strip()[:20]
            product_id = str(product.get('product_id', '')).strip()[:100]
            name = str(product.get('name', 'Unknown Product')).strip()[:500]

            # Convert prices safely
            try:
                current_price = float(product.get('current_price', 0))
                current_price = max(0.0, current_price)  # Ensure non-negative
            except (ValueError, TypeError):
                current_price = 0.0

            try:
                original_price = float(product.get('original_price', current_price))
                original_price = max(0.0, original_price)
            except (ValueError, TypeError):
                original_price = current_price

            # Convert rating safely (0-5 scale)
            try:
                rating = float(product.get('rating', 0))
                rating = max(0.0, min(5.0, rating))  # Clamp to 0-5
            except (ValueError, TypeError):
                rating = 0.0

            # Convert review count safely
            try:
                review_count = int(product.get('review_count', 0))
                review_count = max(0, review_count)  # Ensure non-negative
            except (ValueError, TypeError):
                review_count = 0

            # Other fields
            store_name = str(product.get('store_name', '')).strip()[:200]
            image_url = str(product.get('image_url', '')).strip()[:500]

            # Get timestamp
            crawled_at = product.get('crawled_at')
            if crawled_at is None:
                from datetime import datetime
                crawled_at = datetime.now()

            # 5. SQL query
            query = """
            INSERT INTO products (
                platform, product_id, name, current_price, original_price,
                rating, review_count, store_name, category, details, image_url, crawled_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                current_price = VALUES(current_price),
                original_price = VALUES(original_price),
                rating = VALUES(rating),
                review_count = VALUES(review_count),
                store_name = VALUES(store_name),
                category = VALUES(category),
                details = VALUES(details),
                image_url = VALUES(image_url),
                last_updated = CURRENT_TIMESTAMP
            """

            # 6. Values tuple
            values = (
                platform, product_id, name,
                current_price, original_price,
                rating, review_count,
                store_name, category,
                details_json, image_url,
                crawled_at
            )

            # 7. Execute
            self.cursor.execute(query, values)
            product_id_in_db = self.cursor.lastrowid

            # 8. If update (not insert), get the actual ID
            if product_id_in_db == 0:
                # Get ID of existing product
                select_query = """
                SELECT id FROM products 
                WHERE platform = %s AND product_id = %s
                """
                self.cursor.execute(select_query, (platform, product_id))
                result = self.cursor.fetchone()
                product_id_in_db = result[0] if result else 0

            # 9. Record price history for trend analysis
            if product_id_in_db > 0 and current_price > 0:
                self._record_price_history(product_id_in_db, current_price)

            # 10. Commit
            self.connection.commit()

            return True

        except mysql.connector.Error as err:
            print(f"❌ MySQL Error in insert/update: {err}")
            if self.connection:
                self.connection.rollback()
            return False
        except Exception as e:
            print(f"❌ General Error in insert/update: {e}")
            import traceback
            traceback.print_exc()
            if self.connection:
                self.connection.rollback()
            return False

    def _record_price_history(self, product_id: int, price: float):
        """Record price in history table for trend analysis"""
        try:
            query = "INSERT INTO price_history (product_id, price) VALUES (%s, %s)"
            self.cursor.execute(query, (product_id, price))
        except mysql.connector.Error as err:
            print(f"⚠️ Price history error: {err}")

    def import_csv_to_database(self, csv_file: str, platform: str = None):
        """
        Import CSV data to MySQL database
        Supports incremental updates and deduplication
        """
        if not os.path.exists(csv_file):
            print(f"❌ CSV file not found: {csv_file}")
            return False

        try:
            # Read CSV with error handling
            df = pd.read_csv(csv_file, on_bad_lines='skip')

            if df.empty:
                print(f"⚠️ CSV file is empty: {csv_file}")
                return False

            print(f"📊 Importing {len(df)} products from {csv_file}")

            # Convert DataFrame to list of dictionaries
            products = df.to_dict('records')

            success_count = 0
            fail_count = 0

            for i, product in enumerate(products, 1):
                try:
                    # Clean the product data
                    product = self._clean_product_data(product, platform)

                    if self.insert_or_update_product(product):
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    print(f"  ⚠️ Product {i} error: {e}")
                    fail_count += 1

                # Progress indicator
                if i % 10 == 0:
                    print(f"  Processed {i}/{len(products)} products...")

            print(f"\n✅ Import complete:")
            print(f"   Successful: {success_count}")
            print(f"   Failed: {fail_count}")

            # Update brand statistics
            if success_count > 0:
                self._update_brand_stats()

            return success_count > 0

        except Exception as e:
            print(f"❌ CSV import error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _clean_product_for_insert(self, product: Dict) -> Dict:
        """Clean product data before insertion"""
        cleaned = product.copy()

        # Fix NaN values
        for key in ['review_count', 'rating', 'current_price', 'original_price']:
            if key in cleaned and (pd.isna(cleaned[key]) or cleaned[key] is None):
                cleaned[key] = 0 if key in ['review_count'] else 0.0

        # Fix JSON details
        if 'details' in cleaned:
            if pd.isna(cleaned['details']) or cleaned['details'] is None:
                cleaned['details'] = '{}'
            elif isinstance(cleaned['details'], str):
                # Try to validate JSON
                try:
                    json.loads(cleaned['details'])
                except:
                    # If invalid, create simple JSON
                    cleaned['details'] = json.dumps({'info': str(cleaned['details'])[:100]})
            else:
                # Convert non-string to JSON
                cleaned['details'] = json.dumps({'data': str(cleaned['details'])[:100]})

        # Standardize platform names
        if 'platform' in cleaned:
            platform = str(cleaned['platform']).strip()
            if platform.lower() == 'jd':
                cleaned['platform'] = 'JD.com'
            elif platform.lower() == 'amazon':
                cleaned['platform'] = 'Amazon'

        return cleaned

    def _update_brand_stats(self):
        """Update brand statistics table"""
        try:
            # Clear old stats
            self.cursor.execute("DELETE FROM brand_stats")

            # Calculate brand statistics
            query = """
            INSERT INTO brand_stats (platform, brand_name, product_count, avg_price, avg_rating)
            SELECT 
                platform,
                CASE 
                    WHEN store_name LIKE '%Apple%' THEN 'Apple'
                    WHEN store_name LIKE '%Samsung%' THEN 'Samsung'
                    WHEN store_name LIKE '%华为%' THEN 'Huawei'
                    WHEN store_name LIKE '%小米%' THEN 'Xiaomi'
                    WHEN store_name LIKE '%戴尔%' THEN 'Dell'
                    WHEN store_name LIKE '%联想%' THEN 'Lenovo'
                    ELSE store_name
                END as brand_name,
                COUNT(*) as product_count,
                AVG(current_price) as avg_price,
                AVG(rating) as avg_rating
            FROM products
            WHERE store_name IS NOT NULL AND store_name != ''
            GROUP BY platform, brand_name
            HAVING COUNT(*) > 0
            """

            self.cursor.execute(query)
            self.connection.commit()
            print("✅ Updated brand statistics")

        except mysql.connector.Error as err:
            print(f"⚠️ Brand stats update error: {err}")

    def get_statistics(self) -> Dict:
        """Get database statistics"""
        if not self.connection:
            return {}

        stats = {}

        try:
            # Total products
            self.cursor.execute("SELECT COUNT(*) FROM products")
            stats['total_products'] = self.cursor.fetchone()[0]

            # Products by platform
            self.cursor.execute("SELECT platform, COUNT(*) FROM products GROUP BY platform")
            stats['by_platform'] = dict(self.cursor.fetchall())

            # Price statistics
            self.cursor.execute("""
                SELECT 
                    MIN(current_price), 
                    MAX(current_price), 
                    AVG(current_price)
                FROM products 
                WHERE current_price > 0
            """)
            min_price, max_price, avg_price = self.cursor.fetchone()
            stats['price_stats'] = {
                'min': float(min_price) if min_price else 0,
                'max': float(max_price) if max_price else 0,
                'avg': float(avg_price) if avg_price else 0
            }

            # Latest updates
            self.cursor.execute("""
                SELECT platform, COUNT(*) 
                FROM products 
                WHERE last_updated >= NOW() - INTERVAL 1 DAY
                GROUP BY platform
            """)
            stats['recent_updates'] = dict(self.cursor.fetchall())

        except mysql.connector.Error as err:
            print(f"⚠️ Statistics error: {err}")

        return stats

    def search_products(self, keyword: str = None, min_price: float = None,
                        max_price: float = None, platform: str = None,
                        limit: int = 50) -> List[Dict]:
        """Search products with filters"""
        if not self.connection:
            return []

        try:
            query = "SELECT * FROM products WHERE 1=1"
            params = []

            if keyword:
                query += " AND (name LIKE %s OR category LIKE %s)"
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            if min_price is not None:
                query += " AND current_price >= %s"
                params.append(min_price)

            if max_price is not None:
                query += " AND current_price <= %s"
                params.append(max_price)

            if platform:
                query += " AND platform = %s"
                params.append(platform)

            query += " ORDER BY last_updated DESC LIMIT %s"
            params.append(limit)

            self.cursor.execute(query, params)
            columns = [desc[0] for desc in self.cursor.description]
            results = [dict(zip(columns, row)) for row in self.cursor.fetchall()]

            # Parse JSON details
            for result in results:
                if result.get('details'):
                    try:
                        result['details'] = json.loads(result['details'])
                    except:
                        result['details'] = {}

            return results

        except mysql.connector.Error as err:
            print(f"❌ Search error: {err}")
            return []

    def get_price_history(self, product_id: int, days: int = 30) -> List[Dict]:
        """Get price history for a product"""
        if not self.connection:
            return []

        try:
            query = """
            SELECT price, recorded_at 
            FROM price_history 
            WHERE product_id = %s AND recorded_at >= NOW() - INTERVAL %s DAY
            ORDER BY recorded_at
            """
            self.cursor.execute(query, (product_id, days))

            return [
                {'price': row[0], 'recorded_at': row[1]}
                for row in self.cursor.fetchall()
            ]

        except mysql.connector.Error as err:
            print(f"❌ Price history error: {err}")
            return []

    def export_to_csv(self, output_file: str = 'data/database_export.csv'):
        """Export database to CSV file"""
        if not self.connection:
            return False

        try:
            # Get all products
            self.cursor.execute("SELECT * FROM products")
            columns = [desc[0] for desc in self.cursor.description]
            rows = self.cursor.fetchall()

            if not rows:
                print("⚠️ No data to export")
                return False

            # Create DataFrame and save to CSV
            df = pd.DataFrame(rows, columns=columns)
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            df.to_csv(output_file, index=False, encoding='utf-8-sig')

            print(f"✅ Exported {len(df)} products to {output_file}")
            return True

        except Exception as e:
            print(f"❌ Export error: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            print("✅ Database connection closed")

    def run_setup(self):
        """Interactive setup wizard - NOW RE-RUNNABLE"""
        print("\n⚙️  DATABASE SETUP WIZARD")
        print("-" * 40)

        # Get credentials
        print("\nEnter MySQL credentials (press Enter for defaults):")
        host = input("Host [localhost]: ").strip() or 'localhost'
        user = input("Username [root]: ").strip() or 'root'
        password = input("Password []: ").strip() or ''
        database = input("Database [ecommerce_db]: ").strip() or 'ecommerce_db'

        # Update config
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database
        }

        # Connect (will create database if needed)
        if self.connect():
            # SAFELY create tables (won't fail if they exist)
            if self.safe_create_tables():
                print("\n✅ Database setup/check complete!")
                return True

        print("\n❌ Database setup failed")
        return False

    def safe_create_tables(self):
        """Safely create tables only if they don't exist"""
        if not self.connection:
            print("❌ Not connected to database")
            return False

        try:
            # Check if tables already exist
            self.cursor.execute("SHOW TABLES LIKE 'products'")
            products_exists = self.cursor.fetchone()

            self.cursor.execute("SHOW TABLES LIKE 'price_history'")
            history_exists = self.cursor.fetchone()

            self.cursor.execute("SHOW TABLES LIKE 'brand_stats'")
            stats_exists = self.cursor.fetchone()

            tables_to_create = []

            if not products_exists:
                tables_to_create.append(("products", self._get_products_table_sql()))
            if not history_exists:
                tables_to_create.append(("price_history", self._get_history_table_sql()))
            if not stats_exists:
                tables_to_create.append(("brand_stats", self._get_stats_table_sql()))

            if not tables_to_create:
                print("✅ All tables already exist")
                return True

            print(f"📊 Creating {len(tables_to_create)} missing tables...")

            for table_name, sql in tables_to_create:
                try:
                    self.cursor.execute(sql)
                    print(f"   Created table: {table_name}")
                except mysql.connector.Error as err:
                    print(f"   ⚠️ Error creating {table_name}: {err}")

            self.connection.commit()
            return True

        except mysql.connector.Error as err:
            print(f"❌ Table check error: {err}")
            return False

    def export_and_preserve(self):
        """Smart export that preserves existing data"""
        # First export current database
        self.export_to_csv('data/database_export.csv')

        # Check if all_products.csv exists
        if os.path.exists('data/all_products.csv'):
            try:
                # Load both files
                db_df = pd.read_csv('data/database_export.csv')
                existing_df = pd.read_csv('data/all_products.csv')

                # Merge (database data takes priority)
                merged_df = pd.concat([existing_df, db_df], ignore_index=True)
                merged_df.drop_duplicates(
                    subset=['product_id', 'platform'],
                    keep='last',
                    inplace=True
                )

                # Save
                merged_df.to_csv('data/all_products.csv', index=False, encoding='utf-8-sig')
                print(f"✅ Merged database data with existing all_products.csv")
                print(f"   Total products: {len(merged_df)}")

            except Exception as e:
                print(f"⚠️ Could not merge, using database export: {e}")
                shutil.copy2('data/database_export.csv', 'data/all_products.csv')
        else:
            shutil.copy2('data/database_export.csv', 'data/all_products.csv')

    def _get_products_table_sql(self):
        return """
        CREATE TABLE products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            platform VARCHAR(20) NOT NULL,
            product_id VARCHAR(100) NOT NULL,
            name VARCHAR(500) NOT NULL,
            current_price DECIMAL(10, 2),
            original_price DECIMAL(10, 2),
            rating DECIMAL(3, 2),
            review_count INT,
            store_name VARCHAR(200),
            category VARCHAR(100),
            details JSON,
            image_url VARCHAR(500),
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_product (platform, product_id),
            INDEX idx_platform (platform),
            INDEX idx_price (current_price),
            INDEX idx_category (category),
            INDEX idx_store (store_name)
        )
        """

    def _get_history_table_sql(self):
        return """
        CREATE TABLE price_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_id INT NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            INDEX idx_product_price (product_id, recorded_at),
            INDEX idx_recorded_at (recorded_at)
        )
        """

    def _get_stats_table_sql(self):
        return """
        CREATE TABLE brand_stats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            platform VARCHAR(20),
            brand_name VARCHAR(100),
            product_count INT DEFAULT 0,
            avg_price DECIMAL(10, 2),
            avg_rating DECIMAL(3, 2),
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_brand (platform, brand_name)
        )
        """

def main():
    """Main function to run database module"""
    print("=" * 60)
    print("🗄️  DATABASE MODULE - MYSQL")
    print("=" * 60)

    # Create database instance
    db = MySQLDatabase()

    # Run setup wizard
    if not db.run_setup():
        return

    # Import existing CSV files
    print("\n📥 IMPORTING EXISTING DATA")
    print("-" * 40)

    csv_files = [
        ('data/amazon_products.csv', 'Amazon'),
        ('data/jd_products.csv', 'JD.com'),
        ('data/all_products.csv', None)
    ]

    for csv_file, platform in csv_files:
        if os.path.exists(csv_file):
            print(f"\nImporting {csv_file}...")
            db.import_csv_to_database(csv_file, platform)
        else:
            print(f"⚠️ File not found: {csv_file}")

    # Show statistics
    print("\n📊 DATABASE STATISTICS")
    print("-" * 40)
    stats = db.get_statistics()

    if stats:
        print(f"Total products: {stats.get('total_products', 0)}")
        print("By platform:")
        for platform, count in stats.get('by_platform', {}).items():
            print(f"  {platform}: {count}")

        price_stats = stats.get('price_stats', {})
        print(f"\nPrice statistics:")
        print(f"  Min: ${price_stats.get('min', 0):.2f}")
        print(f"  Max: ${price_stats.get('max', 0):.2f}")
        print(f"  Avg: ${price_stats.get('avg', 0):.2f}")

    # Export to CSV (for submission)
    print("\n💾 EXPORTING FOR SUBMISSION")
    print("-" * 40)
    db.export_to_csv()

    # Close connection
    db.close()

    print("\n" + "=" * 60)
    print("✅ DATABASE MODULE COMPLETE")

if __name__ == "__main__":
    main()