"""
Views para la app tickets
Actualizado para SaaS: Filtros por Empresa, CRM Seguro y Dashboard Multi-tenant
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, F, DecimalField, OuterRef, Subquery, Max, Count, Prefetch  # ✅ Agregados Count y Prefetch
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.permissions import IsActiveSubscription # <--- NUEVO IMPORT

from .models import Cliente, Ticket, TicketItem, EstadoHistorial
from .serializers import (
    ClienteSerializer, ClienteListSerializer, ClienteCRMSerializer,
    TicketSerializer, TicketListSerializer, TicketCreateSerializer,
    TicketItemSerializer, EstadoHistorialSerializer, TicketUpdateEstadoSerializer
)
from core.mixins import resolver_sede_desde_request

from core.views import BaseTenantViewSet


from .services import ClienteService, TicketService

class ClienteViewSet(BaseTenantViewSet):
    queryset = Cliente.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_documento', 'nombres', 'apellidos', 'telefono', 'email']
    ordering_fields = ['creado_en', 'nombres', 'apellidos', 'ultima_visita']
    ordering = ['-creado_en']
    
    def get_queryset(self):
        # Delegamos la lógica de filtrado y anotaciones al servicio
        empresa = self.request.user.perfil.empresa
        is_list = (self.action == 'list')
        return ClienteService.get_clientes_with_stats(empresa, is_list=is_list)

    def get_serializer_class(self):
        if self.action == 'list':
            return ClienteCRMSerializer
        return ClienteSerializer
    
    @action(detail=True, methods=['get'])
    def tickets(self, request, pk=None):
        cliente = self.get_object() 
        tickets = cliente.tickets.filter(activo=True, empresa=cliente.empresa)
        serializer = TicketListSerializer(tickets, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def soft_delete(self, request, pk=None):
        cliente = self.get_object()
        ClienteService.soft_delete(cliente)
        return Response({'status': 'Cliente eliminado'})
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        cliente = ClienteService.restore(pk, request.user.perfil.empresa)
        if cliente:
            return Response({'status': 'Cliente restaurado'})
        return Response({'error': 'Cliente no encontrado o activo'}, status=404)


class TicketViewSet(BaseTenantViewSet):
    queryset = Ticket.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_ticket', 'cliente__nombres', 'cliente__apellidos', 'cliente__numero_documento']
    ordering_fields = ['fecha_recepcion', 'fecha_prometida', 'estado']
    ordering = ['-fecha_recepcion']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TicketListSerializer
        elif self.action == 'create':
            return TicketCreateSerializer
        elif self.action == 'update_estado':
            return TicketUpdateEstadoSerializer
        return TicketSerializer

    def get_queryset(self):
        # Delegamos filtrado, sede y anotaciones financieras al servicio
        empresa = self.request.user.perfil.empresa
        sede = resolver_sede_desde_request(self.request)
        
        # Recopilar filtros de query_params
        filters_dict = {
            'estado': self.request.query_params.get('estado'),
            'prioridad': self.request.query_params.get('prioridad'),
            'cliente_id': self.request.query_params.get('cliente'),
            'fecha_desde': self.request.query_params.get('fecha_desde'),
            'fecha_hasta': self.request.query_params.get('fecha_hasta'),
            'pendientes_pago': self.request.query_params.get('pendientes_pago'),
        }
        
        return TicketService.get_filtered_tickets(empresa, sede, filters_dict)
    
    def list(self, request, *args, **kwargs):
        # Mantenemos el mapeo de ultimo_metodo_pago si no está en el serializer base
        response = super().list(request, *args, **kwargs)
        data_list = response.data['results'] if 'results' in response.data else response.data
        
        # El servicio anotó el queryset con 'ultimo_metodo_pago'
        # Si el serializer no lo incluye, lo agregamos manualmente aquí (o actualizar serializer)
        if isinstance(data_list, list):
            # Obtener el mapeo directamente del queryset anotado
            queryset = self.filter_queryset(self.get_queryset())
            # Optimizamos: solo iteramos sobre los IDs cargados en esta página
            page_ids = [item['id'] for item in data_list]
            ticket_map = {t.id: t.ultimo_metodo_pago for t in queryset.filter(id__in=page_ids)}
            
            for item in data_list:
                item['ultimo_metodo_pago'] = ticket_map.get(item['id'])
            
        return response

    def perform_create(self, serializer):
        # Primero realizar creación estándar (asociar empresa/sede) via BaseTenantViewSet
        super().perform_create(serializer)
        
        # Enviar notificación de creación
        from notificaciones.services import EmailService
        EmailService.send_ticket_notification(serializer.instance, tipo='CREACION')

    @action(detail=True, methods=['post'])
    def update_estado(self, request, pk=None):
        ticket = self.get_object() 
        serializer = TicketUpdateEstadoSerializer(data=request.data, context={'ticket': ticket})
        
        if serializer.is_valid():
            nuevo_estado = serializer.validated_data['estado']
            comentario = serializer.validated_data.get('comentario', '')
            
            exito, mensaje = TicketService.update_estado(ticket, nuevo_estado, request.user, comentario)
            
            if not exito:
                return Response({'error': mensaje}, status=status.HTTP_400_BAD_REQUEST)
            
            # Enviar notificación si el estado es LISTO o ENTREGADO
            from notificaciones.services import EmailService
            if nuevo_estado == 'LISTO':
                EmailService.send_ticket_notification(ticket, tipo='LISTO')
            elif nuevo_estado == 'ENTREGADO':
                EmailService.send_ticket_notification(ticket, tipo='ENTREGADO')
            
            return Response({
                'status': 'Estado actualizado',
                'estado_nuevo': nuevo_estado,
                'ticket': TicketSerializer(ticket, context={'request': request}).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def agregar_item(self, request, pk=None):
        ticket = self.get_object()
        serializer = TicketItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                ticket=ticket, 
                empresa=ticket.empresa, 
                creado_por=request.user
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def imprimir(self, request, pk=None):
        ticket = self.get_object()
        serializer = TicketSerializer(ticket, context={'request': request})
        return Response({'ticket': serializer.data, 'mensaje': 'Datos para impresión'})
    
    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        ticket = self.get_object()
        exito, mensaje = TicketService.cancel_ticket(ticket, request.user, request.data.get('motivo'))
        
        if not exito:
            return Response({'error': mensaje}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response({'status': 'Ticket cancelado'})
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        tickets_activos = self.get_queryset()
        stats = TicketService.get_dashboard_stats(tickets_activos)
        return Response(stats)