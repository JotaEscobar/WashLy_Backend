from django.contrib import admin
from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'canal', 'destinatario', 'estado', 'intentos', 'creado_en')
    list_filter = ('canal', 'estado', 'empresa')
    search_fields = ('destinatario', 'asunto', 'mensaje')
    readonly_fields = ('creado_en', 'fecha_envio')
    date_hierarchy = 'creado_en'
