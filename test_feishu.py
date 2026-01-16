import asyncio
import sys
from datetime import datetime

# Ensure the current directory is in the path so we can import duetto
sys.path.append(".")

from duetto.config import settings
from duetto.models import Alert, AlertType, AlertPriority
from duetto.services.feishu import FeishuService

async def main():
    print("--- Duetto Feishu Notification Test ---")
    
    # Check if URL is configured
    if not settings.feishu_webhook_url:
        print("❌ Error: DUETTO_FEISHU_WEBHOOK_URL is not set.")
        print("Please set it in your .env file or environment variables.")
        return

    print(f"✅ Webhook URL found: {settings.feishu_webhook_url[:10]}...******")

    service = FeishuService()
    
    # Create a mock alert
    alert = Alert(
        id="test_alert_001",
        type=AlertType.SEC_8K,
        priority=AlertPriority.HIGH,
        ticker="TEST",
        company="Duetto Test Corp",
        title="🔔 Duetto Feishu Integration Test",
        summary="This is a **test message** sent from the Duetto Verification Script.\nIf you see this, the Feishu integration is working correctly.",
        url="https://github.com/duetto",
        source="Verification Script",
        timestamp=datetime.utcnow(),
        raw_data={}
    )
    
    print("📤 Sending test alert...")
    try:
        await service.send_alert(alert)
        print("✅ Alert sent successfully (check your Feishu group).")
    except Exception as e:
        print(f"❌ Failed to send alert: {e}")
    finally:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
