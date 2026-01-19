from django.contrib import admin
from .models import Empresa, Sede

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    # CORRECCIÓN: Cambiado 'is_subscription_active' por 'es_valida' (tu variable real)
    list_display = ('nombre', 'ruc', 'plan', 'estado', 'fecha_vencimiento', 'es_valida')
    list_filter = ('estado', 'plan')
    search_fields = ('nombre', 'ruc')
    readonly_fields = ('fecha_inicio',)
    
    fieldsets = (
        ('Datos Principales', {
            'fields': ('nombre', 'ruc', 'logo', 'moneda', 'zona_horaria')
        }),
        ('Contacto', {
            'fields': ('direccion_fiscal', 'telefono_contacto', 'email_contacto')
        }),
        ('Suscripción SaaS', {
            'fields': ('plan', 'estado', 'fecha_vencimiento', 'fecha_inicio')
        }),
        ('Configuración Tickets', {
            'fields': ('ticket_prefijo', 'ticket_dias_entrega', 'ticket_mensaje_pie')
        }),
        ('Configuración Global', {
            # Agregué SMS también porque tu modelo original lo tiene
            'fields': ('stock_minimo_global', 'notif_email_activas', 'notif_whatsapp_activas', 'notif_sms_activas')
        }),
    )

@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'empresa', 'telefono', 'activo')
    list_filter = ('empresa', 'activo')
    search_fields = ('nombre', 'codigo', 'direccion')