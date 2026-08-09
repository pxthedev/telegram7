import io

import qrcode


def make_pix_qr(emv_code: str) -> bytes:
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(emv_code)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
