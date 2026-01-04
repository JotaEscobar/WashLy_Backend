from django.contrib import admin
from .models import CategoriaProducto, Producto, MovimientoInventario, AlertaStock

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'stock_actual', 'unidad_medida', 'precio_compra')
    search_fields = ('nombre', 'codigo')
    list_filter = ('categoria',)

@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('producto', 'tipo', 'cantidad', 'creado_en', 'creado_por')
    list_filter = ('tipo', 'creado_en')

# Registramos los simples
admin.site.register(CategoriaProducto)
admin.site.register(AlertaStock)