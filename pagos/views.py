from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Pago, CajaSesion, MovimientoCaja
from .serializers import PagoSerializer, CajaSesionSerializer, MovimientoCajaSerializer

class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_pago', 'ticket__numero_ticket', 'ticket__cliente_nombre', 'ticket__cliente_telefono']
    ordering = ['-fecha_pago']

    def perform_create(self, serializer):
        # Al crear un pago (generalmente desde Tickets o POS), se vincula el usuario
        serializer.save(creado_por=self.request.user)

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        pago = self.get_object()
        # Lógica de Extorno: Cambia estado y libera saldo en ticket (si implementas esa lógica en ticket)
        pago.estado = 'ANULADO'
        pago.save()
        
        # Aquí podrías llamar a un signal o método para actualizar el saldo del ticket
        ticket = pago.ticket
        # ticket.saldo_pendiente += pago.monto ... (Esto ya depende de tu modelo Ticket)
        # ticket.save()
        
        return Response({'status': 'Pago anulado'})

class CajaViewSet(viewsets.ModelViewSet):
    queryset = CajaSesion.objects.all()
    serializer_class = CajaSesionSerializer

    @action(detail=False, methods=['get'])
    def mi_caja(self, request):
        # Devuelve la caja ABIERTA del usuario actual
        caja = CajaSesion.objects.filter(usuario=request.user, estado='ABIERTA').first()
        if caja:
            return Response(self.get_serializer(caja).data)
        return Response(None) # No hay caja

    @action(detail=False, methods=['post'])
    def abrir(self, request):
        if CajaSesion.objects.filter(usuario=request.user, estado='ABIERTA').exists():
            return Response({'error': 'Ya tienes una caja abierta'}, status=400)
        
        caja = CajaSesion.objects.create(
            usuario=request.user,
            monto_inicial=request.data.get('monto_inicial', 0),
            estado='ABIERTA'
        )
        return Response(self.get_serializer(caja).data)

    @action(detail=True, methods=['post'])
    def cerrar(self, request, pk=None):
        caja = self.get_object()
        caja.monto_real = request.data.get('monto_real', 0)
        caja.comentarios = request.data.get('comentarios', '')
        
        # Calculamos sistema al momento del cierre
        serializer = self.get_serializer(caja)
        caja.monto_sistema = serializer.data['saldo_actual'] 
        caja.diferencia = caja.monto_real - caja.monto_sistema
        
        caja.estado = 'CERRADA'
        caja.fecha_cierre = timezone.now()
        caja.save()
        return Response(self.get_serializer(caja).data)

    @action(detail=True, methods=['post'])
    def movimiento(self, request, pk=None):
        caja = self.get_object()
        MovimientoCaja.objects.create(
            caja=caja,
            tipo=request.data.get('tipo'), # INGRESO / EGRESO
            monto=request.data.get('monto'),
            descripcion=request.data.get('descripcion'),
            categoria=request.data.get('categoria', 'GENERAL'),
            creado_por=request.user
        )
        return Response({'status': 'Movimiento registrado'})