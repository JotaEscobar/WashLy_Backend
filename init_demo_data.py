"""
Script para inicializar datos de demostración
Ejecutar: python manage.py shell < init_demo_data.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Washly.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Sede
from tickets.models import Cliente
from servicios.models import (
    CategoriaServicio, Servicio, TipoPrenda, Prenda, PrecioPorPrenda
)
from inventario.models import CategoriaProducto, Producto

print("Iniciando carga de datos de demostración...")

# Crear superusuario si no existe
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@washly.pe', 'admin123')
    print("✓ Superusuario creado: admin/admin123")

# Crear sede
sede, created = Sede.objects.get_or_create(
    codigo='SEDE01',
    defaults={
        'nombre': 'Washly - Miraflores',
        'direccion': 'Av. Larco 123, Miraflores, Lima',
        'telefono': '01-4567890',
        'email': 'miraflores@washly.pe',
        'horario_apertura': '08:00',
        'horario_cierre': '20:00'
    }
)
print(f"{'✓ Sede creada' if created else '• Sede ya existe'}: {sede.nombre}")

# Crear categorías de servicio
categorias = {
    'LAV': 'Lavado',
    'PLA': 'Planchado',
    'SEC': 'Lavado en Seco',
    'TIN': 'Tintorería'
}

for codigo, nombre in categorias.items():
    cat, created = CategoriaServicio.objects.get_or_create(
        nombre=nombre,
        defaults={'orden': list(categorias.keys()).index(codigo)}
    )
    print(f"{'✓' if created else '•'} Categoría: {nombre}")

# Crear servicios
servicios_data = [
    ('Lavado Básico', 'LAV-BAS', 'Lavado', 5.00, 60, True),
    ('Lavado Premium', 'LAV-PRE', 'Lavado', 8.00, 60, True),
    ('Planchado Simple', 'PLA-SIM', 'Planchado', 3.00, 30, True),
    ('Planchado Delicado', 'PLA-DEL', 'Planchado', 5.00, 45, True),
    ('Lavado en Seco', 'SEC-001', 'Lavado en Seco', 15.00, 120, True),
    ('Tintorería', 'TIN-001', 'Tintorería', 20.00, 240, True),
]

for nombre, codigo, cat_nombre, precio, tiempo, req_prenda in servicios_data:
    categoria = CategoriaServicio.objects.get(nombre=cat_nombre)
    servicio, created = Servicio.objects.get_or_create(
        codigo=codigo,
        defaults={
            'nombre': nombre,
            'categoria': categoria,
            'precio_base': precio,
            'tiempo_estimado': tiempo,
            'requiere_prenda': req_prenda,
            'disponible': True
        }
    )
    if created:
        servicio.sedes.add(sede)
    print(f"{'✓' if created else '•'} Servicio: {nombre}")

# Crear tipos de prenda
tipos_prenda = ['Camisa', 'Pantalón', 'Vestido', 'Falda', 'Saco', 'Abrigo', 'Ropa de Cama']
for nombre in tipos_prenda:
    tipo, created = TipoPrenda.objects.get_or_create(nombre=nombre)
    print(f"{'✓' if created else '•'} Tipo Prenda: {nombre}")

# Crear prendas específicas
prendas_data = [
    ('Camisa manga corta', 'Camisa', 1.0),
    ('Camisa manga larga', 'Camisa', 1.2),
    ('Pantalón casual', 'Pantalón', 1.0),
    ('Pantalón de vestir', 'Pantalón', 1.3),
    ('Vestido corto', 'Vestido', 1.5),
    ('Vestido largo', 'Vestido', 2.0),
    ('Falda', 'Falda', 1.0),
    ('Saco', 'Saco', 1.8),
    ('Abrigo', 'Abrigo', 2.5),
    ('Sábana', 'Ropa de Cama', 1.2),
    ('Edredón', 'Ropa de Cama', 2.0),
]

for nombre, tipo_nombre, multiplicador in prendas_data:
    tipo = TipoPrenda.objects.get(nombre=tipo_nombre)
    prenda, created = Prenda.objects.get_or_create(
        nombre=nombre,
        tipo=tipo,
        defaults={'multiplicador_precio': multiplicador}
    )
    print(f"{'✓' if created else '•'} Prenda: {nombre}")

# Crear categorías de productos
cat_productos = ['Detergentes', 'Suavizantes', 'Blanqueadores', 'Empaque', 'Limpieza']
for nombre in cat_productos:
    cat, created = CategoriaProducto.objects.get_or_create(nombre=nombre)
    print(f"{'✓' if created else '•'} Categoría Producto: {nombre}")

# Crear productos de inventario
productos_data = [
    ('Detergente Industrial 5L', 'DET-001', 'Detergentes', 'L', 50, 10),
    ('Suavizante Premium 5L', 'SUA-001', 'Suavizantes', 'L', 30, 10),
    ('Blanqueador 1L', 'BLA-001', 'Blanqueadores', 'L', 20, 5),
    ('Bolsas Plásticas (100 und)', 'BOL-001', 'Empaque', 'PAQUETE', 10, 3),
    ('Perchas (50 und)', 'PER-001', 'Empaque', 'PAQUETE', 5, 2),
]

for nombre, codigo, cat_nombre, unidad, stock, stock_min in productos_data:
    categoria = CategoriaProducto.objects.get(nombre=cat_nombre)
    prod, created = Producto.objects.get_or_create(
        codigo=codigo,
        defaults={
            'nombre': nombre,
            'categoria': categoria,
            'unidad_medida': unidad,
            'stock_actual': stock,
            'stock_minimo': stock_min,
            'sede': sede
        }
    )
    print(f"{'✓' if created else '•'} Producto: {nombre}")

# Crear clientes de ejemplo
clientes_data = [
    ('DNI', '12345678', 'Juan', 'Pérez García', '987654321', 'juan@email.com'),
    ('DNI', '87654321', 'María', 'López Rojas', '987654322', 'maria@email.com'),
    ('DNI', '11223344', 'Carlos', 'Mendoza Silva', '987654323', 'carlos@email.com'),
]

for tipo_doc, num_doc, nombres, apellidos, tel, email in clientes_data:
    cliente, created = Cliente.objects.get_or_create(
        numero_documento=num_doc,
        defaults={
            'tipo_documento': tipo_doc,
            'nombres': nombres,
            'apellidos': apellidos,
            'telefono': tel,
            'email': email,
            'sede': sede
        }
    )
    print(f"{'✓' if created else '•'} Cliente: {nombres} {apellidos}")

print("\n✅ Datos de demostración cargados exitosamente!")
print("\nCredenciales de acceso:")
print("Usuario: admin")
print("Password: admin123")
print("\nAccede al admin en: http://localhost:8000/admin/")
print("Accede a la API en: http://localhost:8000/api/")
