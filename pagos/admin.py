from django.contrib import admin
from .models import Pago, CajaSesion, MovimientoCaja, MetodoPagoConfig


@admin.register(MetodoPagoConfig)
class MetodoPagoConfigAdmin(admin.ModelAdmin):
    list_display = ('nombre_mostrar', 'codigo_metodo', 'empresa', 'activo')
    list_filter = ('codigo_metodo', 'activo', 'empresa')
    search_fields = ('nombre_mostrar', 'numero_cuenta')


@admin.register(CajaSesion)
class CajaSesionAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'sede', 'estado', 'fecha_apertura', 'monto_inicial')
    list_filter = ('estado', 'empresa', 'sede')
    search_fields = ('usuario__username',)
    readonly_fields = ('fecha_apertura',)
    date_hierarchy = 'fecha_apertura'


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('numero_pago', 'ticket', 'monto', 'metodo_pago_snapshot', 'estado', 'fecha_pago')
    list_filter = ('estado', 'metodo_pago_snapshot', 'empresa')
    search_fields = ('numero_pago', 'ticket__numero_ticket', 'referencia')
    readonly_fields = ('numero_pago', 'fecha_pago')
    date_hierarchy = 'fecha_pago'


@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    list_display = ('id', 'caja', 'tipo', 'monto', 'descripcion', 'categoria')
    list_filter = ('tipo', 'categoria', 'empresa')
    search_fields = ('descripcion',)
