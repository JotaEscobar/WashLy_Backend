"""
Utilidades comunes del sistema ERP Washly
"""

import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
import random
import string
from datetime import datetime


def generar_numero_unico(prefijo='', longitud=4): 
    """
    Genera un número único más corto.
    Formato: PREFIJO-YYMMDD-1234
    Ejemplo: TKT-240104-8821
    """
    fecha = datetime.now().strftime('%y%m%d') 
    aleatorio = ''.join(random.choices(string.digits, k=longitud))
    
    if prefijo:
        return f"{prefijo}-{fecha}-{aleatorio}"
    return f"{fecha}-{aleatorio}"


def generar_qr_code(data, filename='qr_code'):
    """
    Genera un código QR y retorna el archivo
    """
    qr = qrcode.QRCode(
        version=settings.QR_CODE_VERSION,
        error_correction=getattr(qrcode.constants, f'ERROR_CORRECT_{settings.QR_CODE_ERROR_CORRECTION}'),
        box_size=settings.QR_CODE_BOX_SIZE,
        border=settings.QR_CODE_BORDER,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return ContentFile(buffer.read(), name=f'{filename}.png')


