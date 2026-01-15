import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Washly.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Empresa, Sede
from usuarios.models import PerfilUsuario
from tickets.models import ConfiguracionTicket
from pagos.models import MetodoPagoConfig
from servicios.models import CategoriaServicio, Servicio, TipoPrenda, Prenda, PrecioPorPrenda
from datetime import timedelta
from django.utils import timezone

def crear_datos_iniciales():
    print("🚀 Iniciando configuración SaaS de prueba...")

    # 1. Crear Empresa (Tenant)
    empresa, created = Empresa.objects.get_or_create(
        ruc="20123456789",
        defaults={
            'nombre': "Lavandería Demo SaaS",
            'direccion_fiscal': "Av. Siempre Viva 123",
            'telefono_contacto': "999888777",
            'email_contacto': "admin@washly.demo",
            'plan': 'PRO',
            'estado': 'ACTIVO',
            'fecha_vencimiento': timezone.now() + timedelta(days=365)
        }
    )
    print(f"✅ Empresa creada: {empresa.nombre}")

    # 2. Configuración Tickets
    ConfiguracionTicket.objects.get_or_create(
        empresa=empresa,
        defaults={'prefijo_ticket': 'WASH'}
    )

    # 3. Crear Métodos de Pago
    metodos = [
        ('EFECTIVO', 'Efectivo', None),
        ('YAPE', 'Yape Admin', '999888777'),
        ('PLIN', 'Plin Admin', '999888777'),
    ]
    for codigo, nombre, cuenta in metodos:
        MetodoPagoConfig.objects.get_or_create(
            empresa=empresa,
            codigo_metodo=codigo,
            numero_cuenta=cuenta,
            defaults={'nombre_mostrar': nombre, 'activo': True}
        )
    print("✅ Métodos de pago configurados")

    # 4. Crear Sede Principal
    sede, _ = Sede.objects.get_or_create(
        empresa=empresa,
        codigo="SEDE-01",
        defaults={
            'nombre': "Sede Central",
            'direccion': "Calle Principal 123",
            'telefono': "012345678",
            'email': "sede1@washly.demo",
            'horario_apertura': "08:00",
            'horario_cierre': "20:00"
        }
    )

    # 5. Crear Superusuario Admin
    username = "admin"
    email = "admin@washly.demo"
    password = "admin" # CAMBIAR EN PRODUCCIÓN

    if not User.objects.filter(username=username).exists():
        user = User.objects.create_superuser(username, email, password)
        print(f"✅ Superusuario creado: {username} / {password}")
    else:
        user = User.objects.get(username=username)

    # 6. Vincular Usuario a Empresa (Perfil)
    PerfilUsuario.objects.get_or_create(
        usuario=user,
        defaults={
            'empresa': empresa,
            'rol': 'ADMIN_NEGOCIO',
            'telefono': '999999999'
        }
    )
    print("✅ Perfil SaaS vinculado")

    # 7. Crear Datos Demo de Servicios (Para que no esté vacío)
    cat_lavado, _ = CategoriaServicio.objects.get_or_create(
        empresa=empresa, nombre="Lavado por Kilo", defaults={'orden': 1}
    )
    cat_prendas, _ = CategoriaServicio.objects.get_or_create(
        empresa=empresa, nombre="Lavado por Prenda", defaults={'orden': 2}
    )

    # Servicio por Kilo
    Servicio.objects.get_or_create(
        empresa=empresa, codigo="LAV-KILO",
        defaults={
            'nombre': "Lavado Completo x Kg", 
            'categoria': cat_lavado,
            'tipo_cobro': 'POR_KILO',
            'precio_base': 5.00,
            'tiempo_estimado': 24
        }
    )

    # Servicio por Prenda (Sastrería/Seco)
    srv_seco, _ = Servicio.objects.get_or_create(
        empresa=empresa, codigo="LAV-SECO",
        defaults={
            'nombre': "Lavado al Seco", 
            'categoria': cat_prendas,
            'tipo_cobro': 'POR_PRENDA',
            'precio_base': 0, # Se define por prenda
            'tiempo_estimado': 48
        }
    )

    # Tipos de Prenda
    tipo_ropa, _ = TipoPrenda.objects.get_or_create(empresa=empresa, nombre="Ropa de Vestir")
    
    # Prendas y Precios
    prendas_data = [
        ('Terno', 25.00),
        ('Camisa', 12.00),
        ('Pantalón', 12.00),
        ('Abrigo', 30.00),
    ]

    for p_nombre, p_precio in prendas_data:
        prenda, _ = Prenda.objects.get_or_create(
            empresa=empresa, tipo=tipo_ropa, nombre=p_nombre
        )
        PrecioPorPrenda.objects.get_or_create(
            empresa=empresa, servicio=srv_seco, prenda=prenda,
            defaults={'precio': p_precio}
        )

    print("✅ Servicios y Precios demo creados")
    print("🎉 ¡SISTEMA SAAS LISTO!")

if __name__ == '__main__':
    crear_datos_iniciales()