from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Pago
from .serializers import PagoSerializer

class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_pago', 'ticket__numero_ticket']
    ordering = ['-fecha_pago']
    
    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        pago = self.get_object()
        pago.estado = 'PAGADO'
        pago.save()
        return Response({'status': 'Pago confirmado'})
    
    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        pago = self.get_object()
        pago.estado = 'CANCELADO'
        pago.save()
        return Response({'status': 'Pago cancelado'})
