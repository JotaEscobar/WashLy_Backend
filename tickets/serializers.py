from rest_framework import serializers
from .models import Cliente, Ticket, TicketItem, EstadoHistorial

class ClienteSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.ReadOnlyField()
    total_gastado = serializers.ReadOnlyField()
    class Meta:
        model = Cliente
        fields = '__all__'
        read_only_fields = ['creado_en', 'fecha_registro']

class ClienteListSerializer(serializers.ModelSerializer):
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
        fields = ['id', 'servicio', 'servicio_nombre', 'prenda', 'prenda_nombre', 'cantidad', 'precio_unitario', 'subtotal', 'descripcion', 'completado', 'creado_en']
        read_only_fields = ['creado_en', 'subtotal']

class EstadoHistorialSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)
    class Meta:
        model = EstadoHistorial
        fields = ['id', 'estado_anterior', 'estado_nuevo', 'fecha_cambio', 'usuario', 'usuario_nombre', 'comentario']
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
            'tipo_entrega',
            'requiere_pago_anticipado', 'empleado_asignado', 'items',
            'historial_estados', 'total', 'saldo_pendiente', 'esta_pagado',
            'creado_en', 'actualizado_en', 'activo'
        ]
        read_only_fields = ['numero_ticket', 'qr_code', 'fecha_recepcion', 'creado_en', 'actualizado_en', 'total', 'saldo_pendiente', 'esta_pagado']
    
    def get_total(self, obj): return float(obj.calcular_total())
    def get_saldo_pendiente(self, obj): return float(obj.calcular_saldo_pendiente())
    def get_esta_pagado(self, obj): return obj.esta_pagado()
    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            if request: return request.build_absolute_uri(obj.qr_code.url)
        return None

# --- ARREGLO 2: AGREGADAS FECHAS (Evita NaN) ---
class TicketListSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    total = serializers.SerializerMethodField()
    saldo_pendiente = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'numero_ticket', 'cliente', 'cliente_nombre', 'estado',
            'prioridad', 'fecha_recepcion', 'fecha_prometida', 'total',
            'saldo_pendiente', 'activo',
            'creado_en', 'actualizado_en' 
        ]
    
    def get_total(self, obj): return float(obj.calcular_total())
    def get_saldo_pendiente(self, obj): return float(obj.calcular_saldo_pendiente())

class TicketCreateSerializer(serializers.ModelSerializer):
    items = TicketItemSerializer(many=True)
    pago_monto = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, write_only=True)
    metodo_pago = serializers.CharField(max_length=50, required=False, write_only=True)

    class Meta:
        model = Ticket
        fields = [
            'id', 'numero_ticket', 'qr_code', 'creado_en',
            'cliente', 'sede', 'prioridad', 'fecha_prometida', 
            'tipo_entrega', 
            'observaciones', 'instrucciones_especiales',
            'requiere_pago_anticipado', 'empleado_asignado', 'items',
            'pago_monto', 'metodo_pago'
        ]
        read_only_fields = ['id', 'numero_ticket', 'qr_code', 'creado_en']
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        pago_monto = validated_data.pop('pago_monto', None)
        metodo_pago = validated_data.pop('metodo_pago', 'EFECTIVO')

        ticket = Ticket.objects.create(**validated_data)
        
        for item_data in items_data:
            TicketItem.objects.create(ticket=ticket, **item_data)
        
        if pago_monto is not None and float(pago_monto) > 0:
            from pagos.models import Pago
            Pago.objects.create(
                ticket=ticket,
                monto=pago_monto,
                metodo_pago=metodo_pago,
                estado='PAGADO',
                referencia=f'Pago inicial Ticket {ticket.numero_ticket}'
            )
        
        return ticket

class TicketUpdateEstadoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=Ticket.ESTADO_CHOICES)
    comentario = serializers.CharField(required=False, allow_blank=True)
    
    def validate_estado(self, value):
        ticket = self.context.get('ticket')
        if ticket:
            transiciones_validas = {
                'RECIBIDO': ['EN_PROCESO', 'CANCELADO'],
                'EN_PROCESO': ['LISTO', 'RECIBIDO', 'CANCELADO'],
                'LISTO': ['ENTREGADO', 'EN_PROCESO', 'CANCELADO'],
                'ENTREGADO': [], 
                'CANCELADO': [], 
            }
            if ticket.estado == value:
                raise serializers.ValidationError("El ticket ya está en este estado")
            if value not in transiciones_validas.get(ticket.estado, []):
                raise serializers.ValidationError(f"No se puede cambiar de {ticket.estado} a {value}")
        return value