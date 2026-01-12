from rest_framework import serializers
from django.db.models import Sum
from django.utils import timezone
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
        """
        Flag para el frontend: 
        Permite anular solo si es de HOY y no está ya anulado.
        """
        es_hoy = obj.fecha_pago.date() == timezone.now().date()
        no_esta_anulado = obj.estado != 'ANULADO'
        return es_hoy and no_esta_anulado

class MovimientoCajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoCaja
        fields = '__all__'
        read_only_fields = ['caja']

class CajaSesionSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)
    
    # Campos calculados
    total_efectivo = serializers.SerializerMethodField()
    total_digital = serializers.SerializerMethodField()
    total_ventas = serializers.SerializerMethodField()
    total_gastos = serializers.SerializerMethodField()
    saldo_actual = serializers.SerializerMethodField()
    
    # Desglose para el cierre detallado
    desglose_pagos = serializers.SerializerMethodField()

    class Meta:
        model = CajaSesion
        fields = '__all__'

    def _get_apertura_dict(self, obj):
        """Helper para obtener el dict de apertura de forma segura"""
        try:
            if isinstance(obj.detalle_apertura, str):
                return json.loads(obj.detalle_apertura)
            return obj.detalle_apertura if obj.detalle_apertura else {}
        except:
            return {}

    def get_total_ventas(self, obj):
        return obj.pagos_ticket.filter(estado='PAGADO').aggregate(Sum('monto'))['monto__sum'] or 0

    def get_total_gastos(self, obj):
        return obj.movimientos_extra.filter(tipo='EGRESO').aggregate(Sum('monto'))['monto__sum'] or 0

    def get_total_efectivo(self, obj):
        # Monto Inicial (Base) + Ventas Efectivo + Ingresos Extra - Gastos
        ventas_efectivo = obj.pagos_ticket.filter(estado='PAGADO', metodo_pago='EFECTIVO').aggregate(Sum('monto'))['monto__sum'] or 0
        ingresos_extra = obj.movimientos_extra.filter(tipo='INGRESO').aggregate(Sum('monto'))['monto__sum'] or 0
        gastos = self.get_total_gastos(obj)
        return obj.monto_inicial + ventas_efectivo + ingresos_extra - gastos

    def get_total_digital(self, obj):
        # Ventas digitales + Saldos iniciales digitales (declarados en apertura)
        ventas_digital = obj.pagos_ticket.filter(estado='PAGADO').exclude(metodo_pago='EFECTIVO').aggregate(Sum('monto'))['monto__sum'] or 0
        
        # Sumar saldos iniciales de apertura que NO sean efectivo (Yape, Plin, etc)
        apertura = self._get_apertura_dict(obj)
        saldo_inicial_digital = 0
        for metodo, monto in apertura.items():
            if metodo != 'EFECTIVO':
                saldo_inicial_digital += float(monto or 0)
                
        return ventas_digital + saldo_inicial_digital

    def get_saldo_actual(self, obj):
        return float(self.get_total_efectivo(obj)) + float(self.get_total_digital(obj))
    
    def get_desglose_pagos(self, obj):
        """
        Retorna los totales por método de pago para el cuadre de caja.
        Considera: Saldo Inicial (Apertura) + Ventas - Gastos (solo efectivo)
        """
        metodos = ['EFECTIVO', 'YAPE', 'PLIN', 'TARJETA', 'TRANSFERENCIA']
        desglose = {}
        apertura = self._get_apertura_dict(obj)
        
        for m in metodos:
            # 1. Ventas del turno
            total_ventas = obj.pagos_ticket.filter(estado='PAGADO', metodo_pago=m).aggregate(Sum('monto'))['monto__sum'] or 0
            
            # 2. Saldo Inicial declarado al abrir
            saldo_inicial = 0
            if m == 'EFECTIVO':
                saldo_inicial = obj.monto_inicial # El efectivo base va en campo directo
            else:
                saldo_inicial = float(apertura.get(m, 0)) # Los digitales van en el JSON
            
            # 3. Cálculo final
            total = saldo_inicial + total_ventas

            # Ajustes específicos para Efectivo (Movimientos Manuales)
            if m == 'EFECTIVO':
                ingresos_extra = obj.movimientos_extra.filter(tipo='INGRESO').aggregate(Sum('monto'))['monto__sum'] or 0
                gastos = self.get_total_gastos(obj)
                total = total + ingresos_extra - gastos
            
            desglose[m] = total
            
        return desglose