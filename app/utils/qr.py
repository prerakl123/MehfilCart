"""QR code generation for restaurant tables."""

# TODO: Install qrcode[pil] in Phase 2: `uv add qrcode[pil]`
# TODO: Implement QR generation that encodes the table join URL


def generate_table_qr_url(restaurant_id: str, table_id: str, base_url: str = "https://mehfilcart.app") -> str:
    """Generate the URL that a table's QR code should encode."""
    return f"{base_url}/join/{restaurant_id}/{table_id}"


# TODO: def generate_qr_image(url: str) -> bytes:
#     """Generate a QR code PNG image for the given URL."""
#     import qrcode
#     qr = qrcode.make(url)
#     buffer = io.BytesIO()
#     qr.save(buffer, format="PNG")
#     return buffer.getvalue()
