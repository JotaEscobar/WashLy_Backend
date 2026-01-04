"""
Serializers para la app tickets
"""

from rest_framework import serializers
from .models import Cliente, Ticket, TicketItem, EstadoHistorial


class ClienteSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.ReadOnlyField()
    total_gastado = serializers.ReadOnlyField()
    
    class Meta:
        model = Cliente
        fields = [
            'id', 'tipo_documento', 'numero_documento', 'nombres', 'apellidos',
            'nombre_completo', 'telefono', 'email', 'direccion', 'fecha_registro',
            'notas', 'preferencias', 'sede', 'activo', 'creado_en',
            'total_gastado'
        ]
        read_only_fields = ['creado_en', 'fecha_registro']


class ClienteListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados"""
    nombre_completo = serializers.ReadOnlyField()
    
    class Meta:
        model = Cliente
        fields = ['id', 'numero_documento', 'nombre_completo', 'telefono', 'email']


class TicketItemSerializer(serializers.ModelSerializer):
    servicio_nombre = serializers.CharField(source='servicio.nombre', read_only=True)
    prenda_nombre = serializers.CharField(source='prenda.nombre', read_only=True)
    subtotal = serializers.ReadOnlyField()
    
    class Meta:
        model = TicketItem
        fields = [
            'id', 'servicio', 'servicio_nombre', 'prenda', 'prenda_nombre',
            'cantidad', 'precio_unitario', 'subtotal', 'descripcion',
            'completado', 'creado_en'
        ]
        read_only_fields = ['creado_en', 'subtotal']


class EstadoHistorialSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)
    
    class Meta:
        model = EstadoHistorial
        fields = [
            'id', 'estado_anterior', 'estado_nuevo', 'fecha_cambio',
            'usuario', 'usuario_nombre', 'comentario'
        ]
        read_only_fields = ['fecha_cambio']


class TicketSerializer(serializers.ModelSerializer):
    items = TicketItemSerializer(many=True, read_only=True)
    cliente_info = ClienteListSerializer(source='cliente', read_only=True)
    historial_estados = EstadoHistorialSerializer(many=True, read_only=True)
    
    total = serializers.SerializerMethodField()
    saldo_pendiente = serializers.SerializerMethodField()
    esta_pagado = serializers.SerializerMethodField()
    qr_code_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'numero_ticket', 'qr_code', 'qr_code_url', 'cliente', 'cliente_info',
            'sede', 'estado', 'prioridad', 'fecha_recepcion', 'fecha_prometida',
            'fecha_entrega', 'observaciones', 'instrucciones_especiales',
            'requiere_pago_anticipado', 'empleado_asignado', 'items',
            'historial_estados', 'total', 'saldo_pendiente', 'esta_pagado',
            'creado_en', 'actualizado_en', 'activo'
        ]
        read_only_fields = [
            'numero_ticket', 'qr_code', 'fecha_recepcion', 'creado_en',
            'actualizado_en', 'total', 'saldo_pendiente', 'esta_pagado'
        ]
    
    def get_total(self, obj):
        return float(obj.calcular_total())
    
    def get_saldo_pendiente(self, obj):
        return float(obj.calcular_saldo_pendiente())
    
    def get_esta_pagado(self, obj):
        return obj.esta_pagado()
    
    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
        return None


class TicketListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados"""
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    total = serializers.SerializerMethodField()
    saldo_pendiente = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'numero_ticket', 'cliente', 'cliente_nombre', 'estado',
            'prioridad', 'fecha_recepcion', 'fecha_prometida', 'total',
            'saldo_pendiente', 'activo'
        ]
    
    def get_total(self, obj):
        return float(obj.calcular_total())
    
    def get_saldo_pendiente(self, obj):
        return float(obj.calcular_saldo_pendiente())


class TicketCreateSerializer(serializers.ModelSerializer):
    """Serializer para creación de tickets con items"""
    items = TicketItemSerializer(many=True)
    
    class Meta:
        model = Ticket
        fields = [
            'cliente', 'sede', 'prioridad', 'fecha_prometida',
            'observaciones', 'instrucciones_especiales',
            'requiere_pago_anticipado', 'empleado_asignado', 'items'
        ]
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        ticket = Ticket.objects.create(**validated_data)
        
        for item_data in items_data:
            TicketItem.objects.create(ticket=ticket, **item_data)
        
        return ticket


class TicketUpdateEstadoSerializer(serializers.Serializer):
    """Serializer para actualizar el estado de un ticket"""
    estado = serializers.ChoiceField(choices=Ticket.ESTADO_CHOICES)
    comentario = serializers.CharField(required=False, allow_blank=True)
    
    def validate_estado(self, value):
        ticket = self.context.get('ticket')
        if ticket:
            # Validar transiciones de estado
            transiciones_validas = {
                'RECIBIDO': ['EN_PROCESO', 'CANCELADO'],
                'EN_PROCESO': ['LISTO', 'RECIBIDO', 'CANCELADO'],
                'LISTO': ['ENTREGADO', 'EN_PROCESO', 'CANCELADO'],
                'ENTREGADO': [],  # No se puede cambiar desde entregado
                'CANCELADO': [],  # No se puede cambiar desde cancelado
            }
            
            if ticket.estado == value:
                raise serializers.ValidationError("El ticket ya está en este estado")
            
            if value not in transiciones_validas.get(ticket.estado, []):
                raise serializers.ValidationError(
                    f"No se puede cambiar de {ticket.estado} a {value}"
                )
        
        return value
