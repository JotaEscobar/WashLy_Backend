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
    # Resumen Financiero en Tiempo Real
    total_efectivo = serializers.SerializerMethodField()
    total_digital = serializers.SerializerMethodField()
    total_ventas = serializers.SerializerMethodField()
    total_gastos = serializers.SerializerMethodField()
    saldo_actual = serializers.SerializerMethodField()

    class Meta:
        model = CajaSesion
        fields = '__all__'

    def get_total_ventas(self, obj):
        # Suma de todos los PAGOS de tickets en estado PAGADO
        return obj.pagos_ticket.filter(estado='PAGADO').aggregate(Sum('monto'))['monto__sum'] or 0

    def get_total_gastos(self, obj):
        # Suma de Egresos manuales
        return obj.movimientos_extra.filter(tipo='EGRESO').aggregate(Sum('monto'))['monto__sum'] or 0

    def get_total_efectivo(self, obj):
        # Saldo Inicial + Ventas Efectivo + Ingresos Extra Efectivo - Gastos Efectivo
        # (Asumimos por simplicidad que Movimientos Extra son Efectivo, o podríamos agregar campo metodo)
        ventas_efectivo = obj.pagos_ticket.filter(estado='PAGADO', metodo_pago='EFECTIVO').aggregate(Sum('monto'))['monto__sum'] or 0
        ingresos_extra = obj.movimientos_extra.filter(tipo='INGRESO').aggregate(Sum('monto'))['monto__sum'] or 0
        gastos = self.get_total_gastos(obj)
        return obj.monto_inicial + ventas_efectivo + ingresos_extra - gastos

    def get_total_digital(self, obj):
        # Ventas por Yape, Plin, Tarjeta, Transferencia
        return obj.pagos_ticket.filter(estado='PAGADO').exclude(metodo_pago='EFECTIVO').aggregate(Sum('monto'))['monto__sum'] or 0

    def get_saldo_actual(self, obj):
        # Dinero total teórico (Efectivo + Digital)
        return self.get_total_efectivo(obj) + self.get_total_digital(obj)