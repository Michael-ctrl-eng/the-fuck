import logging

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import get_settings
from app.models.order import Order
from app.models.tenant import Tenant

settings = get_settings()
logger = logging.getLogger(__name__)


async def notify_new_order(tenant: Tenant, order: Order) -> None:
    """Send notification to tenant owner about a new order."""
    if tenant.notification_pref == "email" and tenant.business_email:
        await _send_email_notification(tenant, order)
    else:
        logger.info(
            f"Order {order.order_number} for tenant {tenant.page_name} — "
            f"notification pref: {tenant.notification_pref}"
        )


async def _send_email_notification(tenant: Tenant, order: Order) -> None:
    """Send order notification email."""
    if not settings.SMTP_USER:
        logger.warning("SMTP not configured, skipping email notification")
        return

    items_text = ""
    for item in order.items:
        items_text += f"  - {item.product_name} x{item.quantity} = ৳{item.total_price}\n"

    body = f"""নতুন অর্ডার পেয়েছেন! (New Order Received!)

Order: {order.order_number}
Customer: {order.customer_name}
Phone: {order.customer_phone}
Address: {order.address_detail}, {order.upazila or ''}, {order.district}, {order.division}
Payment: {order.payment_method.upper()}

Items:
{items_text}
Subtotal: ৳{order.subtotal}
Delivery: ৳{order.delivery_charge}
Total: ৳{order.total}

---
Mama Sales Agent
"""

    msg = MIMEMultipart()
    msg["From"] = settings.NOTIFICATION_FROM_EMAIL
    msg["To"] = tenant.business_email
    msg["Subject"] = f"[{tenant.page_name}] New Order {order.order_number} - ৳{order.total}"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=True,
        )
        logger.info(f"Email sent for order {order.order_number}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
