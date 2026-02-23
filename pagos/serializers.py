"""
Serializers para la app pagos
Actualizado para SaaS: Soporte dinámico de métodos de pago y seguridad multi-tenant
"""

from rest_framework import serializers
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal
from .models import Pago, CajaSesion, MovimientoCaja, MetodoPagoConfig
import json

class MetodoPagoConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetodoPagoConfig
        fields = '__all__'
        read_only_fields = ['empresa']

class PagoSerializer(serializers.ModelSerializer):
    ticket_numero = serializers.CharField(source='ticket.numero_ticket', read_only=True)
    cliente_nombre = serializers.CharField(source='ticket.cliente.nombre_completo', read_only=True)
    # Mostramos el nombre histórico del método por si la configuración se borra a futuro
    metodo_nombre = serializers.CharField(source='metodo_pago_snapshot', read_only=True)
    es_anulable = serializers.SerializerMethodField()
    
    class Meta:
        model = Pago
        fields = '__all__'
        read_only_fields = ['numero_pago', 'caja', 'empresa', 'creado_por', 'metodo_pago_snapshot', 'es_anulable']

    def get_es_anulable(self, obj):
        # Validar anulación solo el mismo día (Hora local Perú)
        hoy = timezone.localtime(timezone.now()).date()
        fecha_pago = timezone.localtime(obj.fecha_pago).date()
        return fecha_pago == hoy and obj.estado != 'ANULADO'

class MovimientoCajaSerializer(serializers.ModelSerializer):
    metodo_nombre = serializers.CharField(source='metodo_pago_config.nombre_mostrar', read_only=True)
    
    class Meta:
        model = MovimientoCaja
        fields = '__all__'
        read_only_fields = ['caja', 'empresa', 'creado_por']

class CajaSesionSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)
    
    # Campos calculados para el Frontend (Dashboard de Caja)
    total_efectivo = serializers.SerializerMethodField()
    total_digital = serializers.SerializerMethodField()
    total_ventas = serializers.SerializerMethodField()
    total_gastos = serializers.SerializerMethodField()
    saldo_actual = serializers.SerializerMethodField()
    desglose_pagos = serializers.SerializerMethodField()

    class Meta:
        model = CajaSesion
        fields = '__all__'
        read_only_fields = ['empresa', 'creado_por', 'monto_final_sistema', 'diferencia']

    def _get_sede_from_context(self):
        """
        Obtiene la sede actual desde el contexto del serializer.
        El contexto debe ser pasado por la view: serializer(obj, context={'sede': sede_obj})
        """
        return self.context.get('sede', None)

    def _get_pagos_qs(self, obj):
        """Retorna queryset de pagos filtrado por sede si aplica."""
        qs = obj.pagos_ticket.filter(estado='PAGADO')
        sede = self._get_sede_from_context()
        if sede:
            qs = qs.filter(ticket__sede=sede)
        return qs

    def _get_movimientos_qs(self, obj):
        """Retorna queryset de movimientos."""
        return obj.movimientos_extra.all()

    def _get_apertura_dict(self, obj):
        try:
            if isinstance(obj.detalle_apertura, str):
                return json.loads(obj.detalle_apertura)
            return obj.detalle_apertura if obj.detalle_apertura else {}
        except:
            return {}

    def get_total_ventas(self, obj):
        val = self._get_pagos_qs(obj).aggregate(Sum('monto'))['monto__sum']
        return Decimal(str(val)) if val is not None else Decimal('0.00')

    def get_total_gastos(self, obj):
        val = obj.movimientos_extra.filter(tipo='EGRESO').aggregate(Sum('monto'))['monto__sum']
        return Decimal(str(val)) if val is not None else Decimal('0.00')

    def get_total_efectivo(self, obj):
        """Calcula el total físico en caja (Billetes y monedas)"""
        
        # 1. Ventas en efectivo (filtradas por sede)
        ventas = self._get_pagos_qs(obj).filter(
            Q(metodo_pago_config__codigo_metodo='EFECTIVO') |
            Q(metodo_pago_config__isnull=True, metodo_pago_snapshot__icontains='Efectivo')
        ).aggregate(Sum('monto'))['monto__sum'] or 0
        
        # 2. Ingresos Manuales
        ingresos = obj.movimientos_extra.filter(
            Q(tipo='INGRESO') &
            (Q(metodo_pago_config__codigo_metodo='EFECTIVO') | Q(metodo_pago_config__isnull=True))
        ).aggregate(Sum('monto'))['monto__sum'] or 0
        
        # 3. Egresos Manuales
        egresos = obj.movimientos_extra.filter(
            Q(tipo='EGRESO') &
            (Q(metodo_pago_config__codigo_metodo='EFECTIVO') | Q(metodo_pago_config__isnull=True))
        ).aggregate(Sum('monto'))['monto__sum'] or 0
        
        return Decimal(obj.monto_inicial) + Decimal(ventas) + Decimal(ingresos) - Decimal(egresos)

    def get_total_digital(self, obj):
        """Calcula el dinero en cuentas (Yape, Plin, Tarjeta, etc.)"""
        
        # 1. Ventas no-efectivo (filtradas por sede)
        ventas = self._get_pagos_qs(obj).exclude(
            Q(metodo_pago_config__codigo_metodo='EFECTIVO') | 
            Q(metodo_pago_config__isnull=True, metodo_pago_snapshot__icontains='Efectivo')
        ).aggregate(Sum('monto'))['monto__sum'] or 0
        
        # 2. Apertura Digital (Si hubo saldo inicial en cuentas)
        apertura = self._get_apertura_dict(obj)
        saldo_inicial_digital = Decimal(0)
        for k, v in apertura.items():
            if k != 'EFECTIVO':
                saldo_inicial_digital += Decimal(str(v or 0))

        # 3. Ingresos Digitales
        ingresos = obj.movimientos_extra.filter(tipo='INGRESO').exclude(
            Q(metodo_pago_config__codigo_metodo='EFECTIVO') | Q(metodo_pago_config__isnull=True)
        ).aggregate(Sum('monto'))['monto__sum'] or 0

        # 4. Egresos Digitales
        egresos = obj.movimientos_extra.filter(tipo='EGRESO').exclude(
            Q(metodo_pago_config__codigo_metodo='EFECTIVO') | Q(metodo_pago_config__isnull=True)
        ).aggregate(Sum('monto'))['monto__sum'] or 0
                
        return Decimal(ventas) + saldo_inicial_digital + Decimal(ingresos) - Decimal(egresos)

    def get_saldo_actual(self, obj):
        return self.get_total_efectivo(obj) + self.get_total_digital(obj)
    
    def get_desglose_pagos(self, obj):
        """
        Genera el desglose DINÁMICO basado en los métodos configurados de la empresa.
        Sustituye la lista hardcodeada anterior.
        """
        # Diccionario base
        desglose = {}
        
        # Aseguramos que EFECTIVO siempre esté inicializado
        desglose['EFECTIVO'] = Decimal(0)
        
        # Helper para sumar al diccionario
        def add_to_desglose(codigo, monto, es_resta=False):
            if codigo not in desglose:
                desglose[codigo] = Decimal(0)
            if es_resta:
                desglose[codigo] -= Decimal(str(monto))
            else:
                desglose[codigo] += Decimal(str(monto))

        # 1. Saldo Inicial
        add_to_desglose('EFECTIVO', obj.monto_inicial)
        apertura = self._get_apertura_dict(obj)
        for k, v in apertura.items():
            if k != 'EFECTIVO':
                add_to_desglose(k, v)

        # 2. Ventas (Pagos) — filtrados por sede si aplica
        pagos = self._get_pagos_qs(obj).select_related('metodo_pago_config')
        for p in pagos:
            code = 'OTROS'
            if p.metodo_pago_config:
                code = p.metodo_pago_config.codigo_metodo
            elif p.metodo_pago_snapshot:
                snap = p.metodo_pago_snapshot.upper()
                if 'EFECTIVO' in snap: code = 'EFECTIVO'
                elif 'YAPE' in snap: code = 'YAPE'
                elif 'PLIN' in snap: code = 'PLIN'
                elif 'TARJETA' in snap: code = 'TARJETA'
                elif 'TRANSFERENCIA' in snap: code = 'TRANSFERENCIA'
            
            add_to_desglose(code, p.monto)

        # 3. Movimientos (Ingresos/Egresos)
        movs = obj.movimientos_extra.all().select_related('metodo_pago_config')
        for m in movs:
            code = m.metodo_pago_config.codigo_metodo if m.metodo_pago_config else 'EFECTIVO'
            if m.tipo == 'INGRESO':
                add_to_desglose(code, m.monto)
            else:
                add_to_desglose(code, m.monto, es_resta=True)
                
        return desglose