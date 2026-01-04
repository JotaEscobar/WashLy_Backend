"""
Admin para la app tickets
"""

from django.contrib import admin
from .models import Cliente, Ticket, TicketItem, EstadoHistorial
from django.utils.html import mark_safe

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['numero_documento', 'nombre_completo', 'telefono', 'email', 'activo', 'creado_en']
    list_filter = ['tipo_documento', 'activo', 'creado_en', 'sede']
    search_fields = ['numero_documento', 'nombres', 'apellidos', 'telefono', 'email']
    readonly_fields = ['creado_en', 'actualizado_en', 'creado_por', 'actualizado_por']

    def codigo_qr_imagen(self, obj):
        if obj.qr_code:
            return mark_safe(f'<img src="{obj.qr_code.url}" width="150" height="150" />')
        return "No generado"
    
    codigo_qr_imagen.short_description = 'Código QR'
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('tipo_documento', 'numero_documento', 'nombres', 'apellidos')
        }),
        ('Contacto', {
            'fields': ('telefono', 'email', 'direccion')
        }),
        ('Información Adicional', {
            'fields': ('sede', 'notas', 'preferencias')
        }),
        ('Estado', {
            'fields': ('activo', 'eliminado_en')
        }),
        ('Auditoría', {
            'fields': ('creado_en', 'creado_por', 'actualizado_en', 'actualizado_por'),
            'classes': ('collapse',)
        }),
    )


class TicketItemInline(admin.TabularInline):
    model = TicketItem
    extra = 1
    fields = ['servicio', 'prenda', 'cantidad', 'precio_unitario', 'completado']


class EstadoHistorialInline(admin.TabularInline):
    model = EstadoHistorial
    extra = 0
    readonly_fields = ['estado_anterior', 'estado_nuevo', 'fecha_cambio', 'usuario']
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'numero_ticket', 'cliente', 'estado', 'prioridad',
        'fecha_recepcion', 'fecha_prometida', 'activo'
    ]
    list_filter = ['estado', 'prioridad', 'activo', 'fecha_recepcion', 'sede']
    search_fields = ['numero_ticket', 'cliente__nombres', 'cliente__apellidos', 'cliente__numero_documento']
    readonly_fields = [
        'numero_ticket', 'qr_code', 'fecha_recepcion', 'creado_en',
        'actualizado_en', 'creado_por', 'actualizado_por'
    ]
    inlines = [TicketItemInline, EstadoHistorialInline]
    
    fieldsets = (
        ('Identificación', {
            'fields': ('numero_ticket', 'qr_code')
        }),
        ('Cliente y Sede', {
            'fields': ('cliente', 'sede', 'empleado_asignado')
        }),
        ('Estado', {
            'fields': ('estado', 'prioridad')
        }),
        ('Fechas', {
            'fields': ('fecha_recepcion', 'fecha_prometida', 'fecha_entrega')
        }),
        ('Detalles', {
            'fields': ('observaciones', 'instrucciones_especiales', 'requiere_pago_anticipado')
        }),
        ('Control', {
            'fields': ('activo', 'eliminado_en')
        }),
        ('Auditoría', {
            'fields': ('creado_en', 'creado_por', 'actualizado_en', 'actualizado_por'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TicketItem)
class TicketItemAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'servicio', 'prenda', 'cantidad', 'precio_unitario', 'subtotal', 'completado']
    list_filter = ['completado', 'servicio', 'creado_en']
    search_fields = ['ticket__numero_ticket', 'descripcion']
    readonly_fields = ['creado_en', 'actualizado_en', 'subtotal']


@admin.register(EstadoHistorial)
class EstadoHistorialAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'estado_anterior', 'estado_nuevo', 'fecha_cambio', 'usuario']
    list_filter = ['estado_anterior', 'estado_nuevo', 'fecha_cambio']
    search_fields = ['ticket__numero_ticket', 'comentario']
    readonly_fields = ['fecha_cambio']
