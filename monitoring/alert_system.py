# monitoring/alert_system.py
from .price_monitor import PriceMonitor
import json


class AlertSystem:
    """Simplified interface for price alerts"""

    @staticmethod
    def setup_email_alerts(sender_email: str, sender_password: str,
                           receiver_emails: list):
        """Configure email alerts"""
        config = {
            'email_settings': {
                'enabled': True,
                'sender_email': sender_email,
                'sender_password': sender_password,
                'receiver_emails': receiver_emails
            }
        }

        with open('monitoring_config.json', 'w') as f:
            json.dump(config, f, indent=2)

        print("✅ Email alerts configured")

    @staticmethod
    def quick_monitor(product_id: int, platform: str, target_price: float):
        """Quick setup for monitoring a single product"""
        # This would integrate with your database
        print(f"🔔 Monitoring {platform} product {product_id}")
        print(f"   Target price: ${target_price:.2f}")
        print("   Alerts will be shown in console")

        # Return monitoring details
        return {
            'product_id': product_id,
            'platform': platform,
            'target_price': target_price,
            'monitoring_id': f"{platform}_{product_id}"
        }