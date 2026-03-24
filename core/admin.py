from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from datetime import timedelta
from .models import Empresa, Sede, HistorialSuscripcion

class HistorialSuscripcionInline(admin.TabularInline):
    model = HistorialSuscripcion
    extra = 0
    fields = ('fecha_pago', 'monto', 'metodo', 'periodo_inicio', 'periodo_fin', 'comprobante_codigo')
    ordering = ('-fecha_pago',)

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ruc', 'plan', 'estado', 'color_vencimiento', 'es_valida')
    list_filter = ('estado', 'plan')
    search_fields = ('nombre', 'ruc')
    readonly_fields = ('fecha_inicio',)
    inlines = [HistorialSuscripcionInline]
    actions = ['renovar_un_mes_accion']

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
            'fields': ('ticket_prefijo', 'ticket_logo', 'ticket_mensaje_pie', 'ticket_servicios_descripcion', 'ticket_disclaimer')
        }),
        ('Configuración Global', {
            'fields': ('stock_minimo_global', 'notif_email_activas', 'notif_whatsapp_activas', 'notif_sms_activas')
        }),
    )

    @admin.display(description="Fecha Vencimiento")
    def color_vencimiento(self, obj):
        if not obj.fecha_vencimiento:
            return "-"
        
        hoy = timezone.now()
        color = "green"
        if obj.fecha_vencimiento < hoy:
            color = "red"
        elif obj.fecha_vencimiento < hoy + timedelta(days=7):
            color = "orange"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.fecha_vencimiento.strftime('%d/%m/%Y')
        )

    @admin.action(description="Renovar 1 Mes (Auto)")
    def renovar_un_mes_accion(self, request, queryset):
        for empresa in queryset:
            # Calcular nuevas fechas
            inicio = empresa.fecha_vencimiento.date() if empresa.fecha_vencimiento and empresa.fecha_vencimiento > timezone.now() else timezone.now().date()
            fin = inicio + timedelta(days=30)
            
            # Crear registro en historial
            HistorialSuscripcion.objects.create(
                empresa=empresa,
                fecha_pago=timezone.now(),
                monto=60.00, # Monto base sugerido
                metodo='TRANSFERENCIA',
                periodo_inicio=inicio,
                periodo_fin=fin,
                observaciones="Renovación rápida desde Admin",
                registrado_por=request.user
            )
        self.message_user(request, f"Se han renovado {queryset.count()} empresas por 30 días.")

@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'empresa', 'telefono', 'activo')
    list_filter = ('empresa', 'activo')
    search_fields = ('nombre', 'codigo', 'direccion')

@admin.register(HistorialSuscripcion)
class HistorialSuscripcionAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'fecha_pago', 'monto', 'metodo', 'periodo_fin')
    list_filter = ('metodo', 'fecha_pago')
    search_fields = ('empresa__nombre', 'comprobante_codigo')