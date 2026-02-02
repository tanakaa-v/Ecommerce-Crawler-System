# monitoring/price_monitor.py
import time
import schedule
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading


class PriceMonitor:
    """
    Real-time price monitoring system
    Monitors price changes and sends alerts
    """

    def __init__(self, db_connection):
        self.db = db_connection
        self.monitored_products = []
        self.alerts_sent = []
        self.running = False

        # Load monitoring configuration
        self.config = self._load_config()

        print("=" * 60)
        print("💰 PRICE MONITORING SYSTEM")
        print("=" * 60)

    def _load_config(self) -> Dict:
        """Load monitoring configuration"""
        default_config = {
            'check_interval_minutes': 60,  # Check every hour
            'price_drop_threshold': 0.1,  # 10% price drop
            'price_increase_threshold': 0.2,  # 20% price increase
            'alert_methods': ['console', 'email'],
            'email_settings': {
                'enabled': False,
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'sender_email': '',
                'sender_password': '',
                'receiver_emails': []
            },
            'tracking_period_days': 7
        }

        # Try to load custom config
        config_file = 'monitoring_config.json'
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
                    print("✅ Loaded custom monitoring configuration")
            except:
                print("⚠️ Using default monitoring configuration")

        return default_config

    def add_product_to_monitor(self, product_id: int, platform: str,
                               target_price: float = None,
                               alert_on_drop: bool = True,
                               alert_on_increase: bool = False):
        """Add a product to monitoring list"""
        product_info = {
            'product_id': product_id,
            'platform': platform,
            'target_price': target_price,
            'alert_on_drop': alert_on_drop,
            'alert_on_increase': alert_on_increase,
            'added_at': datetime.now(),
            'last_price': 0,
            'last_checked': None
        }

        self.monitored_products.append(product_info)
        print(f"🔔 Added product {product_id} to monitoring")

        # Save to file
        self._save_monitoring_list()

        return product_info

    def remove_product_from_monitor(self, product_id: int):
        """Remove product from monitoring"""
        self.monitored_products = [
            p for p in self.monitored_products
            if p['product_id'] != product_id
        ]
        print(f"🔕 Removed product {product_id} from monitoring")
        self._save_monitoring_list()

    def check_price_changes(self):
        """Check for price changes on monitored products"""
        if not self.monitored_products:
            print("⚠️ No products being monitored")
            return []

        print(f"\n🔍 Checking {len(self.monitored_products)} monitored products...")

        alerts = []

        for product in self.monitored_products[:10]:  # Limit to 10 for demo
            try:
                # Get current price from database
                current_price = self._get_current_price(
                    product['product_id'],
                    product['platform']
                )

                if not current_price:
                    continue

                # Get historical prices
                history = self._get_price_history(
                    product['product_id'],
                    days=self.config['tracking_period_days']
                )

                if len(history) < 2:
                    # Not enough history yet
                    product['last_price'] = current_price
                    product['last_checked'] = datetime.now()
                    continue

                # Calculate price changes
                previous_price = history[-2]['price'] if len(history) >= 2 else current_price
                price_change = current_price - previous_price
                price_change_percent = (price_change / previous_price) * 100 if previous_price > 0 else 0

                # Check for alerts
                alert = None

                # Price drop alert
                if (product['alert_on_drop'] and price_change_percent < 0 and
                        abs(price_change_percent) >= self.config['price_drop_threshold'] * 100):
                    alert = self._create_alert(
                        product, current_price, previous_price,
                        price_change_percent, 'PRICE_DROP'
                    )

                # Price increase alert
                elif (product['alert_on_increase'] and price_change_percent > 0 and
                      price_change_percent >= self.config['price_increase_threshold'] * 100):
                    alert = self._create_alert(
                        product, current_price, previous_price,
                        price_change_percent, 'PRICE_INCREASE'
                    )

                # Target price alert
                elif (product['target_price'] and
                      current_price <= product['target_price'] and
                      previous_price > product['target_price']):
                    alert = self._create_alert(
                        product, current_price, previous_price,
                        price_change_percent, 'TARGET_REACHED'
                    )

                if alert:
                    alerts.append(alert)
                    self._send_alert(alert)

                # Update product info
                product['last_price'] = current_price
                product['last_checked'] = datetime.now()

            except Exception as e:
                print(f"⚠️ Error monitoring product {product['product_id']}: {e}")

        # Save updated monitoring list
        self._save_monitoring_list()

        if alerts:
            print(f"✅ Generated {len(alerts)} price alerts")
        else:
            print("✅ No significant price changes detected")

        return alerts

    def _get_current_price(self, product_id: int, platform: str) -> Optional[float]:
        """Get current price from database"""
        try:
            # This would query your database
            # For now, simulate with random data
            import random
            return random.uniform(50, 2000)
        except:
            return None

    def _get_price_history(self, product_id: int, days: int = 7) -> List[Dict]:
        """Get price history for a product"""
        try:
            # This would query your price_history table
            # For demo, generate sample data
            import random
            from datetime import datetime, timedelta

            history = []
            base_price = random.uniform(100, 1000)

            for i in range(days):
                date = datetime.now() - timedelta(days=i)
                price = base_price * random.uniform(0.9, 1.1)  # ±10% variation
                history.append({
                    'date': date,
                    'price': round(price, 2)
                })

            return sorted(history, key=lambda x: x['date'])
        except:
            return []

    def _create_alert(self, product: Dict, current_price: float,
                      previous_price: float, change_percent: float,
                      alert_type: str) -> Dict:
        """Create alert object"""
        alert = {
            'product_id': product['product_id'],
            'platform': product['platform'],
            'alert_type': alert_type,
            'current_price': current_price,
            'previous_price': previous_price,
            'change_percent': change_percent,
            'target_price': product.get('target_price'),
            'timestamp': datetime.now(),
            'message': self._generate_alert_message(
                product, current_price, previous_price,
                change_percent, alert_type
            )
        }

        self.alerts_sent.append(alert)
        return alert

    def _generate_alert_message(self, product: Dict, current_price: float,
                                previous_price: float, change_percent: float,
                                alert_type: str) -> str:
        """Generate human-readable alert message"""
        product_name = f"Product {product['product_id']}"

        if alert_type == 'PRICE_DROP':
            return (f"📉 PRICE DROP ALERT: {product_name}\n"
                    f"   Price dropped by {abs(change_percent):.1f}%\n"
                    f"   From: ${previous_price:.2f}\n"
                    f"   To: ${current_price:.2f}\n"
                    f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        elif alert_type == 'PRICE_INCREASE':
            return (f"📈 PRICE INCREASE ALERT: {product_name}\n"
                    f"   Price increased by {change_percent:.1f}%\n"
                    f"   From: ${previous_price:.2f}\n"
                    f"   To: ${current_price:.2f}")

        elif alert_type == 'TARGET_REACHED':
            return (f"🎯 TARGET PRICE REACHED: {product_name}\n"
                    f"   Current price: ${current_price:.2f}\n"
                    f"   Target price: ${product['target_price']:.2f}\n"
                    f"   You should buy now!")

    def _send_alert(self, alert: Dict):
        """Send alert through configured methods"""
        print(f"\n🚨 ALERT: {alert['message']}")

        # Send via configured methods
        for method in self.config['alert_methods']:
            if method == 'email' and self.config['email_settings']['enabled']:
                self._send_email_alert(alert)
            elif method == 'console':
                pass  # Already printed to console
            elif method == 'file':
                self._save_alert_to_file(alert)

    def _send_email_alert(self, alert: Dict):
        """Send alert via email"""
        try:
            settings = self.config['email_settings']

            if not settings['enabled']:
                return

            msg = MIMEMultipart()
            msg['From'] = settings['sender_email']
            msg['To'] = ', '.join(settings['receiver_emails'])
            msg['Subject'] = f"Price Alert: {alert['alert_type']}"

            body = alert['message']
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(settings['smtp_server'], settings['smtp_port'])
            server.starttls()
            server.login(settings['sender_email'], settings['sender_password'])
            server.send_message(msg)
            server.quit()

            print("   📧 Email alert sent")

        except Exception as e:
            print(f"   ⚠️ Failed to send email: {e}")

    def _save_alert_to_file(self, alert: Dict):
        """Save alert to log file"""
        try:
            os.makedirs('monitoring/alerts', exist_ok=True)

            filename = f"monitoring/alerts/alerts_{datetime.now().strftime('%Y%m')}.json"

            # Load existing alerts
            existing_alerts = []
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    existing_alerts = json.load(f)

            # Add new alert
            existing_alerts.append(alert)

            # Save
            with open(filename, 'w') as f:
                json.dump(existing_alerts, f, indent=2, default=str)

            print(f"   💾 Alert saved to {filename}")

        except Exception as e:
            print(f"   ⚠️ Failed to save alert: {e}")

    def _save_monitoring_list(self):
        """Save monitoring list to file"""
        try:
            os.makedirs('monitoring', exist_ok=True)

            with open('monitoring/monitored_products.json', 'w') as f:
                json.dump(self.monitored_products, f, indent=2, default=str)

        except Exception as e:
            print(f"⚠️ Failed to save monitoring list: {e}")

    def start_monitoring(self):
        """Start continuous monitoring"""
        print("\n▶️ STARTING CONTINUOUS MONITORING")
        print(f"   Check interval: {self.config['check_interval_minutes']} minutes")
        print("   Press Ctrl+C to stop\n")

        self.running = True

        # Schedule regular checks
        schedule.every(self.config['check_interval_minutes']).minutes.do(
            self.check_price_changes
        )

        # Run immediately once
        self.check_price_changes()

        # Keep running
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            print("\n⏹️ Monitoring stopped by user")
            self.stop_monitoring()

    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        schedule.clear()
        print("⏹️ Price monitoring stopped")

    def get_monitoring_stats(self) -> Dict:
        """Get monitoring statistics"""
        return {
            'monitored_products': len(self.monitored_products),
            'alerts_sent': len(self.alerts_sent),
            'last_alert': self.alerts_sent[-1] if self.alerts_sent else None,
            'is_running': self.running
        }


def main():
    """Demo of price monitoring system"""
    print("Testing Price Monitoring System...")

    # Create monitor instance (pass your database connection)
    monitor = PriceMonitor(db_connection=None)

    # Add some products to monitor
    monitor.add_product_to_monitor(
        product_id=1001,
        platform='Amazon',
        target_price=999.99,
        alert_on_drop=True,
        alert_on_increase=True
    )

    monitor.add_product_to_monitor(
        product_id=2002,
        platform='JD.com',
        target_price=1999.99,
        alert_on_drop=True
    )

    # Check once
    print("\n🔍 Running one-time check...")
    alerts = monitor.check_price_changes()

    if alerts:
        print(f"\n✅ Generated {len(alerts)} alerts")
    else:
        print("\n✅ No alerts generated")

    # Show stats
    stats = monitor.get_monitoring_stats()
    print(f"\n📊 Monitoring Statistics:")
    print(f"   Products monitored: {stats['monitored_products']}")
    print(f"   Total alerts sent: {stats['alerts_sent']}")
    print(f"   System running: {stats['is_running']}")

    print("\n✅ Price Monitoring System Ready!")


if __name__ == "__main__":
    main()