from rest_framework import serializers
from django.db.models import Sum
from .models import Pago, CajaSesion, MovimientoCaja

class PagoSerializer(serializers.ModelSerializer):
    ticket_numero = serializers.CharField(source='ticket.numero_ticket', read_only=True)
    cliente_nombre = serializers.CharField(source='ticket.cliente_info.nombre_completo', read_only=True)
    
    class Meta:
        model = Pago
        fields = '__all__'
        read_only_fields = ['numero_pago', 'caja']

class MovimientoCajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoCaja
        fields = '__all__'
        read_only_fields = ['caja']

class CajaSesionSerializer(serializers.ModelSerializer):
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

    def get_total_ventas(self, obj):
        return obj.pagos_ticket.filter(estado='PAGADO').aggregate(Sum('monto'))['monto__sum'] or 0

    def get_total_gastos(self, obj):
        return obj.movimientos_extra.filter(tipo='EGRESO').aggregate(Sum('monto'))['monto__sum'] or 0

    def get_total_efectivo(self, obj):
        ventas_efectivo = obj.pagos_ticket.filter(estado='PAGADO', metodo_pago='EFECTIVO').aggregate(Sum('monto'))['monto__sum'] or 0
        ingresos_extra = obj.movimientos_extra.filter(tipo='INGRESO').aggregate(Sum('monto'))['monto__sum'] or 0
        gastos = self.get_total_gastos(obj)
        return obj.monto_inicial + ventas_efectivo + ingresos_extra - gastos

    def get_total_digital(self, obj):
        return obj.pagos_ticket.filter(estado='PAGADO').exclude(metodo_pago='EFECTIVO').aggregate(Sum('monto'))['monto__sum'] or 0

    def get_saldo_actual(self, obj):
        return self.get_total_efectivo(obj) + self.get_total_digital(obj)
    
    def get_desglose_pagos(self, obj):
        """
        Retorna los totales por método de pago para el cuadre de caja.
        """
        # Incluimos los métodos usados en el POS + Transferencia (por si acaso viene de backend)
        metodos = ['EFECTIVO', 'YAPE', 'PLIN', 'TARJETA', 'TRANSFERENCIA']
        desglose = {}
        
        for m in metodos:
            total = obj.pagos_ticket.filter(estado='PAGADO', metodo_pago=m).aggregate(Sum('monto'))['monto__sum'] or 0
            
            # Al efectivo le sumamos la base y movimientos manuales
            if m == 'EFECTIVO':
                ingresos_extra = obj.movimientos_extra.filter(tipo='INGRESO').aggregate(Sum('monto'))['monto__sum'] or 0
                gastos = self.get_total_gastos(obj)
                total = obj.monto_inicial + total + ingresos_extra - gastos
            
            desglose[m] = total
            
        return desglose