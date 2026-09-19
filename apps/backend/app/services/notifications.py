import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, messaging as fcm_messaging
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("firebase-admin not installed, push notifications disabled")


def init_firebase():
    """Initialize Firebase Admin SDK if credentials are configured."""
    if not FIREBASE_AVAILABLE:
        return False
    if not settings.FIREBASE_CREDENTIALS_PATH:
        logger.info("FIREBASE_CREDENTIALS_PATH not set, push notifications disabled")
        return False
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized")
        return True
    except Exception as e:
        logger.error(f"Failed to init Firebase: {e}")
        return False


class NotificationService:
    def __init__(self):
        self._firebase_ready = init_firebase()

    async def send_signal_notification(self, fcm_token: str, signal: dict) -> bool:
        """Send push notification for a new trading signal."""
        if not self._firebase_ready or not FIREBASE_AVAILABLE:
            logger.info(f"[MOCK NOTIFICATION] Signal for {signal.get('pair')}: {signal.get('direction')} @ {signal.get('entry_price')}")
            return True

        try:
            pair = signal.get("pair", "")
            direction = signal.get("direction", "").upper()
            entry = signal.get("entry_price", 0)
            tp = signal.get("take_profit")
            sl = signal.get("stop_loss")
            strategy_name = signal.get("strategy_name", "")
            reason = signal.get("reason", "")

            title = f"Sinyal {direction} {pair}"
            body_parts = [f"Entry: {entry:.4f}"]
            if tp:
                body_parts.append(f"TP: {tp:.4f}")
            if sl:
                body_parts.append(f"SL: {sl:.4f}")
            body = " | ".join(body_parts)

            message = fcm_messaging.Message(
                notification=fcm_messaging.Notification(title=title, body=body),
                data={
                    "pair": str(pair),
                    "direction": str(direction),
                    "entry_price": str(entry),
                    "take_profit": str(tp) if tp else "",
                    "stop_loss": str(sl) if sl else "",
                    "strategy_name": str(strategy_name),
                    "reason": str(reason)[:200],
                    "type": "signal",
                },
                token=fcm_token,
                android=fcm_messaging.AndroidConfig(priority="high"),
                apns=fcm_messaging.APNSConfig(
                    payload=fcm_messaging.APNSPayload(
                        aps=fcm_messaging.Aps(sound="default", badge=1)
                    )
                ),
            )

            response = fcm_messaging.send(message)
            logger.info(f"FCM notification sent: {response}")
            return True

        except Exception as e:
            logger.error(f"Failed to send FCM notification: {e}")
            return False

    async def send_batch_notifications(self, fcm_tokens: list[str], title: str, body: str, data: dict = None) -> int:
        """Send notification to multiple tokens. Returns success count."""
        if not self._firebase_ready or not FIREBASE_AVAILABLE:
            return 0

        try:
            message = fcm_messaging.MulticastMessage(
                notification=fcm_messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                tokens=fcm_tokens[:500],  # FCM limit per batch
            )
            response = fcm_messaging.send_each_for_multicast(message)
            return response.success_count
        except Exception as e:
            logger.error(f"Batch notification error: {e}")
            return 0
