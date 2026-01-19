from rest_framework import serializers
from .models import Empresa, Sede

class EmpresaSerializer(serializers.ModelSerializer):
    direccion = serializers.CharField(source='direccion_fiscal', required=False, allow_blank=True)
    telefono = serializers.CharField(source='telefono_contacto', required=False, allow_blank=True)
    activo = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = [
            'id', 'nombre', 'ruc', 'direccion_fiscal', 
            'logo', 'moneda', 'plan', 'estado', 
            'telefono_contacto', 'email_contacto',
            'ticket_prefijo', 'ticket_dias_entrega', 'ticket_mensaje_pie',
            'stock_minimo_global', 'notif_email_activas',
            'direccion', 'telefono', 'activo'
        ]
        read_only_fields = ['plan', 'fecha_vencimiento']

    def get_activo(self, obj):
        return obj.estado == 'ACTIVO'

class SedeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sede
        fields = '__all__'
        read_only_fields = ['empresa', 'creado_por', 'actualizado_por']