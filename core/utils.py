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


def formatear_numero_telefono_pe(numero):
    """
    Formatea número de teléfono para Perú
    """
    # Remover espacios y caracteres especiales
    numero_limpio = ''.join(filter(str.isdigit, numero))
    
    # Si empieza con 51, ya tiene código de país
    if numero_limpio.startswith('51'):
        return f'+{numero_limpio}'
    
    # Si empieza con 9 (celular), agregar +51
    if numero_limpio.startswith('9') and len(numero_limpio) == 9:
        return f'+51{numero_limpio}'
    
    # Si es número fijo, agregar +51
    if len(numero_limpio) == 7 or len(numero_limpio) == 8:
        return f'+51{numero_limpio}'
    
    return numero


def calcular_tiempo_estimado(servicios):
    """
    Calcula el tiempo estimado total para un conjunto de servicios
    """
    tiempo_total = 0
    for servicio in servicios:
        tiempo_total += servicio.tiempo_estimado
    return tiempo_total


def validar_ruc_dni_peru(documento):
    """
    Valida RUC o DNI de Perú
    """
    if not documento.isdigit():
        return False
    
    # DNI: 8 dígitos
    if len(documento) == 8:
        return True
    
    # RUC: 11 dígitos
    if len(documento) == 11:
        return True
    
    return False
