from rest_framework import serializers
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
from .models import Pago, CajaSesion, MovimientoCaja
import json

class PagoSerializer(serializers.ModelSerializer):
    ticket_numero = serializers.CharField(source='ticket.numero_ticket', read_only=True)
    cliente_nombre = serializers.CharField(source='ticket.cliente_info.nombre_completo', read_only=True)
    es_anulable = serializers.SerializerMethodField()
    
    class Meta:
        model = Pago
        fields = '__all__'
        read_only_fields = ['numero_pago', 'caja', 'es_anulable']

    def get_es_anulable(self, obj):
        # Usar localtime para que coincida con la fecha de Perú (o la del servidor local)
        hoy = timezone.localtime(timezone.now()).date()
        fecha_pago = timezone.localtime(obj.fecha_pago).date()
        return fecha_pago == hoy and obj.estado != 'ANULADO'

class MovimientoCajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoCaja
        fields = '__all__'
        read_only_fields = ['caja']

class CajaSesionSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)
    
    total_efectivo = serializers.SerializerMethodField()
    total_digital = serializers.SerializerMethodField()
    total_ventas = serializers.SerializerMethodField()
    total_gastos = serializers.SerializerMethodField()
    saldo_actual = serializers.SerializerMethodField()
    desglose_pagos = serializers.SerializerMethodField()

    class Meta:
        model = CajaSesion
        fields = '__all__'

    def _get_apertura_dict(self, obj):
        try:
            if isinstance(obj.detalle_apertura, str):
                return json.loads(obj.detalle_apertura)
            return obj.detalle_apertura if obj.detalle_apertura else {}
        except:
            return {}

    def get_total_ventas(self, obj):
        val = obj.pagos_ticket.filter(estado='PAGADO').aggregate(Sum('monto'))['monto__sum']
        return Decimal(str(val)) if val is not None else Decimal('0.00')

    def get_total_gastos(self, obj):
        val = obj.movimientos_extra.filter(tipo='EGRESO').aggregate(Sum('monto'))['monto__sum']
        return Decimal(str(val)) if val is not None else Decimal('0.00')

    def get_total_efectivo(self, obj):
        ventas_efectivo_val = obj.pagos_ticket.filter(estado='PAGADO', metodo_pago='EFECTIVO').aggregate(Sum('monto'))['monto__sum']
        ventas_efectivo = Decimal(str(ventas_efectivo_val)) if ventas_efectivo_val is not None else Decimal('0.00')
        
        ingresos_extra_val = obj.movimientos_extra.filter(tipo='INGRESO').aggregate(Sum('monto'))['monto__sum']
        ingresos_extra = Decimal(str(ingresos_extra_val)) if ingresos_extra_val is not None else Decimal('0.00')
        
        gastos = self.get_total_gastos(obj)
        monto_inicial = Decimal(str(obj.monto_inicial))
        
        return monto_inicial + ventas_efectivo + ingresos_extra - gastos

    def get_total_digital(self, obj):
        ventas_digital_val = obj.pagos_ticket.filter(estado='PAGADO').exclude(metodo_pago='EFECTIVO').aggregate(Sum('monto'))['monto__sum']
        ventas_digital = Decimal(str(ventas_digital_val)) if ventas_digital_val is not None else Decimal('0.00')
        
        apertura = self._get_apertura_dict(obj)
        saldo_inicial_digital = Decimal('0.00')
        for metodo, monto in apertura.items():
            if metodo != 'EFECTIVO':
                saldo_inicial_digital += Decimal(str(monto or 0))
                
        return ventas_digital + saldo_inicial_digital

    def get_saldo_actual(self, obj):
        return self.get_total_efectivo(obj) + self.get_total_digital(obj)
    
    def get_desglose_pagos(self, obj):
        metodos = ['EFECTIVO', 'YAPE', 'PLIN', 'TARJETA', 'TRANSFERENCIA']
        desglose = {}
        apertura = self._get_apertura_dict(obj)
        
        for m in metodos:
            val_ventas = obj.pagos_ticket.filter(estado='PAGADO', metodo_pago=m).aggregate(Sum('monto'))['monto__sum']
            total_ventas = Decimal(str(val_ventas)) if val_ventas is not None else Decimal('0.00')
            
            if m == 'EFECTIVO':
                saldo_inicial = Decimal(str(obj.monto_inicial))
            else:
                saldo_inicial = Decimal(str(apertura.get(m, 0)))
            
            total = saldo_inicial + total_ventas

            if m == 'EFECTIVO':
                val_ingresos = obj.movimientos_extra.filter(tipo='INGRESO').aggregate(Sum('monto'))['monto__sum']
                ingresos_extra = Decimal(str(val_ingresos)) if val_ingresos is not None else Decimal('0.00')
                gastos = self.get_total_gastos(obj)
                total = total + ingresos_extra - gastos
            
            desglose[m] = total
            
        return desglose