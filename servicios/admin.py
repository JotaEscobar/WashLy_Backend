from django.contrib import admin
from .models import CategoriaServicio, Servicio, TipoPrenda, Prenda, Promocion, PrecioPorPrenda

@admin.register(CategoriaServicio)
class CategoriaServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'orden')
    search_fields = ('nombre',)
    ordering = ('orden',)

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio_base', 'activo')
    list_filter = ('categoria', 'activo')
    search_fields = ('nombre',)

@admin.register(TipoPrenda)
class TipoPrendaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')

@admin.register(Prenda)
class PrendaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'activo')
    list_filter = ('tipo',)
    search_fields = ('nombre',)

@admin.register(PrecioPorPrenda)
class PrecioPorPrendaAdmin(admin.ModelAdmin):
    list_display = ('servicio', 'prenda', 'precio')
    list_filter = ('servicio', 'prenda')

@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'valor_descuento', 'activa')
    list_filter = ('activa', 'tipo')
    search_fields = ('nombre', 'codigo')