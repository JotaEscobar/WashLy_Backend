from rest_framework import serializers
from .models import Empresa, Sede, HistorialSuscripcion

class EmpresaSerializer(serializers.ModelSerializer):
    direccion = serializers.CharField(source='direccion_fiscal', read_only=True)
    telefono = serializers.CharField(source='telefono_contacto', read_only=True)
    activo = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = [
            'id', 'nombre', 'ruc', 'direccion_fiscal', 
            'logo', 'moneda', 'plan', 'estado', 'fecha_vencimiento',
            'telefono_contacto', 'email_contacto',
            'ticket_prefijo', 'ticket_mensaje_pie',
            'ticket_servicios_descripcion', 'ticket_disclaimer', 'ticket_logo',
            'stock_minimo_global', 
            'notif_email_activas', 'email_host', 'email_port', 'email_use_tls', 'email_host_user', 'email_host_password',
            'notif_event_creacion', 'notif_event_listo', 'notif_event_entregado',
            'direccion', 'telefono', 'activo'
        ]
        read_only_fields = ['plan', 'fecha_vencimiento']
        extra_kwargs = {
            'email_host_password': {'write_only': True}
        }

    def get_activo(self, obj):
        return obj.estado == 'ACTIVO'

class SedeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sede
        fields = '__all__'
        read_only_fields = ['empresa', 'creado_por', 'actualizado_por']

class HistorialSuscripcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistorialSuscripcion
        fields = '__all__'