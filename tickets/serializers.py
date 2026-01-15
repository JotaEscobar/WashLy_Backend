"""
Serializers para la app tickets
Actualizado para SaaS (Multi-tenant) y Pagos Dinámicos
"""

from rest_framework import serializers
from django.utils import timezone
from django.db.models import Sum
from .models import Cliente, Ticket, TicketItem, EstadoHistorial
from pagos.models import CajaSesion, Pago, MetodoPagoConfig

# --- SERIALIZERS DE CLIENTE ---

class ClienteSerializer(serializers.ModelSerializer):
    """Serializer básico para CRUD de clientes"""
    nombre_completo = serializers.ReadOnlyField()
    total_gastado = serializers.ReadOnlyField()
    
    class Meta:
        model = Cliente
        fields = '__all__'
        # SAAS: empresa y creado_por son automáticos
        read_only_fields = ['creado_en', 'fecha_registro', 'empresa', 'creado_por']

class ClienteListSerializer(serializers.ModelSerializer):
    """Serializer ligero para dropdowns y selecciones simples"""
    nombre_completo = serializers.ReadOnlyField()
    class Meta:
        model = Cliente
        fields = ['id', 'numero_documento', 'nombre_completo', 'telefono', 'email']

class ClienteCRMSerializer(serializers.ModelSerializer):
    """
    Serializer ROBUSTO para el módulo de Clientes (Directorio).
    Incluye indicadores de negocio calculados al vuelo.
    """
    nombre_completo = serializers.ReadOnlyField()
    ultima_visita = serializers.DateTimeField(read_only=True)
    saldo_pendiente = serializers.SerializerMethodField()
    es_vip = serializers.SerializerMethodField()
    
    class Meta:
        model = Cliente
        fields = [
            'id', 'tipo_documento', 'numero_documento', 
            'nombre_completo', 'nombres', 'apellidos', 'telefono', 'email', 'direccion', 
            'ultima_visita', 'saldo_pendiente', 'es_vip', 
            'notas', 'preferencias', 'creado_en'
        ]
    
    def get_saldo_pendiente(self, obj):
        deuda = 0
        # SAAS: Filtrar solo tickets de la misma empresa (por integridad)
        tickets_activos = obj.tickets.filter(empresa=obj.empresa).exclude(estado='CANCELADO')
        for ticket in tickets_activos:
            deuda += ticket.calcular_saldo_pendiente()
        return float(deuda)

    def get_es_vip(self, obj):
        # Lógica VIP: Gasto > 200 en el mes actual
        hoy = timezone.now()
        inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        total_mes = 0
        tickets = obj.tickets.filter(empresa=obj.empresa) # Filtro SaaS
        
        for ticket in tickets:
            pagos_mes = ticket.pagos.filter(
                estado='PAGADO',
                fecha_pago__gte=inicio_mes
            ).aggregate(total=Sum('monto'))['total'] or 0
            total_mes += pagos_mes
            
        return total_mes > 200

# --- SERIALIZERS DE TICKET Y OTROS ---

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
        read_only_fields = ['creado_en', 'subtotal', 'empresa', 'creado_por']

class EstadoHistorialSerializer(serializers.ModelSerializer):
    # En AuditModel el usuario es creado_por
    usuario_nombre = serializers.CharField(source='creado_por.username', read_only=True)
    
    class Meta:
        model = EstadoHistorial
        fields = [
            'id', 'estado_anterior', 'estado_nuevo', 'fecha_cambio', 
            'usuario_nombre', 'comentario'
        ]
        read_only_fields = ['fecha_cambio', 'empresa', 'creado_por']

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
        read_only_fields = [
            'numero_ticket', 'qr_code', 'fecha_recepcion', 'creado_en', 
            'actualizado_en', 'total', 'saldo_pendiente', 'esta_pagado',
            'empresa', 'creado_por'
        ]
    
    def get_total(self, obj): return float(obj.calcular_total())
    def get_saldo_pendiente(self, obj): return float(obj.calcular_saldo_pendiente())
    def get_esta_pagado(self, obj): return obj.esta_pagado()
    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            if request: return request.build_absolute_uri(obj.qr_code.url)
        return None

class TicketListSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    total = serializers.SerializerMethodField()
    saldo_pendiente = serializers.SerializerMethodField()
    es_extornable = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'numero_ticket', 'cliente', 'cliente_nombre', 'estado',
            'prioridad', 'fecha_recepcion', 'fecha_prometida', 'total',
            'saldo_pendiente', 'activo',
            'creado_en', 'actualizado_en',
            'es_extornable'
        ]
    
    def get_total(self, obj): return float(obj.calcular_total())
    def get_saldo_pendiente(self, obj): return float(obj.calcular_saldo_pendiente())
    
    def get_es_extornable(self, obj):
        # Valida si tiene pagos hoy que puedan ser anulados
        hoy = timezone.localtime(timezone.now()).date()
        pagos_hoy = obj.pagos.filter(estado='PAGADO') # related_name='pagos'
        
        for p in pagos_hoy:
             if timezone.localtime(p.fecha_pago).date() == hoy:
                 return True
        return False

class TicketCreateSerializer(serializers.ModelSerializer):
    items = TicketItemSerializer(many=True)
    
    # Campos para el pago inicial (opcional)
    pago_monto = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, write_only=True)
    metodo_pago_id = serializers.IntegerField(required=False, write_only=True) # ID de MetodoPagoConfig
    
    # Legacy support (si el frontend aún envía string)
    metodo_pago_str = serializers.CharField(max_length=50, required=False, write_only=True)

    class Meta:
        model = Ticket
        fields = [
            'id', 'numero_ticket', 'qr_code', 'creado_en',
            'cliente', 'sede', 'prioridad', 'fecha_prometida', 
            'tipo_entrega', 
            'observaciones', 'instrucciones_especiales',
            'requiere_pago_anticipado', 'empleado_asignado', 'items',
            'pago_monto', 'metodo_pago_id', 'metodo_pago_str'
        ]
        read_only_fields = ['id', 'numero_ticket', 'qr_code', 'creado_en', 'empresa', 'creado_por']
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        pago_monto = validated_data.pop('pago_monto', None)
        metodo_pago_id = validated_data.pop('metodo_pago_id', None)
        metodo_pago_str = validated_data.pop('metodo_pago_str', None) # Legacy
        
        request = self.context.get('request')
        user = request.user
        empresa = user.perfil.empresa # Obtenemos empresa del usuario
        
        # Validar Caja si hay pago
        caja_abierta = None
        metodo_config = None
        
        if pago_monto and float(pago_monto) > 0:
            caja_abierta = CajaSesion.objects.filter(
                usuario=user, 
                empresa=empresa, 
                estado='ABIERTA'
            ).first()
            
            if not caja_abierta:
                raise serializers.ValidationError({
                    "error": "No tienes una caja abierta. Apertura caja para recibir pagos."
                })
            
            # Buscar configuración del método de pago
            if metodo_pago_id:
                metodo_config = MetodoPagoConfig.objects.filter(id=metodo_pago_id, empresa=empresa).first()
            elif metodo_pago_str:
                # Intento de fallback inteligente: buscar por código
                metodo_config = MetodoPagoConfig.objects.filter(
                    codigo_metodo=metodo_pago_str.upper(), 
                    empresa=empresa
                ).first()

        # Crear Ticket (Asignando empresa y usuario)
        ticket = Ticket.objects.create(
            empresa=empresa,
            creado_por=user,
            **validated_data
        )
        
        # Crear Items
        for item_data in items_data:
            TicketItem.objects.create(
                ticket=ticket, 
                empresa=empresa, 
                creado_por=user, 
                **item_data
            )
        
        # Registrar Pago Inicial
        if pago_monto and float(pago_monto) > 0:
            Pago.objects.create(
                ticket=ticket,
                caja=caja_abierta,
                monto=pago_monto,
                metodo_pago_config=metodo_config,
                metodo_pago_snapshot=metodo_config.nombre_mostrar if metodo_config else (metodo_pago_str or "EFECTIVO"),
                estado='PAGADO',
                referencia=f'Pago inicial Ticket {ticket.numero_ticket}',
                empresa=empresa,
                creado_por=user
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