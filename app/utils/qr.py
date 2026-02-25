"""QR code generation for restaurant tables."""
import io

import qrcode

from app import settings


def generate_table_qr_url(restaurant_id: str, table_id: str, base_url: str = settings.APP_BASE_URL) -> str:
    """Generate the URL that a table's QR code should encode."""
    return f"{base_url}/join/{restaurant_id}/{table_id}"


def generate_qr_image(url: str) -> bytes:
    """Generate a QR code PNG image for the given URL."""
    qr = qrcode.make(url)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    return buffer.getvalue()
