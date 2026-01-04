from rest_framework import serializers
from .models import Notificacion

class NotificacionSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    ticket_numero = serializers.CharField(source='ticket.numero_ticket', read_only=True)
    
    class Meta:
        model = Notificacion
        fields = '__all__'
