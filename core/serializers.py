from rest_framework import serializers
from .models import Empresa, Sede

class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = [
            'id', 'nombre', 'ruc', 'direccion_fiscal', 
            'logo', 'moneda', 'plan', 'estado', 
            'telefono_contacto', 'email_contacto',
            # Nuevos campos de configuración
            'ticket_prefijo', 'ticket_dias_entrega', 'ticket_mensaje_pie',
            'stock_minimo_global', 'notif_email_activas'
        ]
        read_only_fields = ['plan', 'estado', 'fecha_vencimiento']

class SedeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sede
        fields = '__all__'
        read_only_fields = ['empresa', 'creado_por', 'actualizado_por']