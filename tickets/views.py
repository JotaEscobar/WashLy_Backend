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

class BaseTenantViewSet(viewsets.ModelViewSet):
    """Clase base para asegurar filtrado por empresa y sede en todas las vistas"""
    permission_classes = [IsAuthenticated, IsActiveSubscription]

    def get_queryset(self):
        # Filtra siempre por la empresa del usuario logueado
        queryset = self.queryset.model.objects.filter(
            empresa=self.request.user.perfil.empresa,
            activo=True
        )
        
        # Filtro por Sede (resuelve header X-Current-Sede-ID a nivel de view/DRF)
        sede = resolver_sede_desde_request(self.request)
        if sede and hasattr(self.queryset.model, 'sede'):
            queryset = queryset.filter(sede=sede)
                
        return queryset

    def perform_create(self, serializer):
        save_kwargs = {
            'empresa': self.request.user.perfil.empresa,
            'creado_por': self.request.user
        }
        
        # Asignar sede si existe en contexto
        sede = resolver_sede_desde_request(self.request)
        if sede and hasattr(self.queryset.model, 'sede'):
            save_kwargs['sede'] = sede
               
        serializer.save(**save_kwargs)
    
    def perform_update(self, serializer):
        # Prevenir cambio de sede
        if 'sede' in serializer.validated_data:
            serializer.validated_data.pop('sede')
            
        serializer.save(actualizado_por=self.request.user)


class ClienteViewSet(BaseTenantViewSet):
    queryset = Cliente.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_documento', 'nombres', 'apellidos', 'telefono', 'email']
    ordering_fields = ['creado_en', 'nombres', 'apellidos', 'ultima_visita']
    ordering = ['-creado_en']
    
    def get_queryset(self):
        # 1. Filtro base por empresa (BaseTenantViewSet)
        queryset = super().get_queryset()
        
        # 2. Optimización CRM: Anotamos la fecha del último ticket
        queryset = queryset.annotate(
            ultima_visita=Max('tickets__fecha_recepcion')
        )
        
        # 3. ✅ Optimización N+1: Solo anotar en listado, prefetch en detalle
        if self.action == 'list':
            # En listado: solo select_related para empresa y agregados
            queryset = queryset.select_related('empresa')
            # Anotar total de tickets y gasto total (sin cargar objetos completos)
            queryset = queryset.annotate(
                total_tickets=Count('tickets'),
                total_gastado=Sum('tickets__pagos__monto', filter=Q(tickets__pagos__estado='PAGADO'))
            )
        elif self.action == 'retrieve':
            # ✅ En detalle: sí cargar relaciones completas
            queryset = queryset.prefetch_related(
                Prefetch('tickets', queryset=Ticket.objects.filter(activo=True).select_related('sede', 'empleado_asignado')),
                'tickets__items',
                'tickets__pagos'
            )
            
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ClienteCRMSerializer
        return ClienteSerializer
    
    @action(detail=True, methods=['get'])
    def tickets(self, request, pk=None):
        cliente = self.get_object() # Ya filtra por empresa
        tickets = cliente.tickets.filter(activo=True, empresa=cliente.empresa)
        serializer = TicketListSerializer(tickets, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def soft_delete(self, request, pk=None):
        cliente = self.get_object()
        cliente.soft_delete()
        return Response({'status': 'Cliente eliminado'})
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        try:
            cliente = Cliente.objects.get(
                pk=pk, 
                empresa=request.user.perfil.empresa,
                activo=False
            )
            cliente.restore()
            return Response({'status': 'Cliente restaurado'})
        except Cliente.DoesNotExist:
            return Response({'error': 'Cliente no encontrado'}, status=404)


class TicketViewSet(BaseTenantViewSet):
    queryset = Ticket.objects.all().select_related(
        'cliente', 'sede', 'empleado_asignado'
    ).prefetch_related('items', 'historial_estados')
    
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
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print("🚨 ERROR DE VALIDACION:", serializer.errors)
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        # 1. Filtro base por empresa
        queryset = super().get_queryset()
        
        # 2. Lógica Financiera (Subqueries seguras)
        from pagos.models import Pago
        
        # Subquery: Último método de pago (de ESTA empresa)
        ult_pago = Pago.objects.filter(
            ticket=OuterRef('pk'),
            empresa=self.request.user.perfil.empresa, 
            estado='PAGADO'
        ).order_by('-fecha_pago')

        queryset = queryset.annotate(
            # Total pagado real
            total_pagado_db=Coalesce(
                Sum('pagos__monto', filter=Q(pagos__estado='PAGADO', pagos__empresa=self.request.user.perfil.empresa)), 
                0, 
                output_field=DecimalField()
            ),
            # Costo total del ticket
            total_ticket_db=Coalesce(
                Sum(F('items__cantidad') * F('items__precio_unitario')),
                0,
                output_field=DecimalField()
            ),
            # Último método usado (snapshot o config)
            ultimo_metodo_pago=Subquery(ult_pago.values('metodo_pago_snapshot')[:1])
        ).distinct() 

        # 3. Filtros Estándar
        estado = self.request.query_params.get('estado', None)
        if estado: queryset = queryset.filter(estado=estado)
        
        prioridad = self.request.query_params.get('prioridad', None)
        if prioridad: queryset = queryset.filter(prioridad=prioridad)
        
        cliente_id = self.request.query_params.get('cliente', None)
        if cliente_id: queryset = queryset.filter(cliente_id=cliente_id)
        
        # Filtros de fecha
        fecha_desde = self.request.query_params.get('fecha_desde', None)
        fecha_hasta = self.request.query_params.get('fecha_hasta', None)
        if fecha_desde: queryset = queryset.filter(fecha_recepcion__date__gte=fecha_desde)
        if fecha_hasta: queryset = queryset.filter(fecha_recepcion__date__lte=fecha_hasta)
        
        # 4. Filtro de Deuda (Pendientes de Pago)
        pendientes_pago = self.request.query_params.get('pendientes_pago', None)
        if pendientes_pago == 'true':
            queryset = queryset.exclude(estado='CANCELADO').filter(
                total_ticket_db__gt=F('total_pagado_db')
            )
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        data_list = response.data['results'] if 'results' in response.data else response.data
        
        tickets_filtrados = self.filter_queryset(self.get_queryset())
        ticket_map = {t.id: t.ultimo_metodo_pago for t in tickets_filtrados}
        
        if isinstance(data_list, list):
            for item in data_list:
                item['ultimo_metodo_pago'] = ticket_map.get(item['id'])
            
        return response

    @action(detail=True, methods=['post'])
    def update_estado(self, request, pk=None):
        ticket = self.get_object() 
        serializer = TicketUpdateEstadoSerializer(data=request.data, context={'ticket': ticket})
        
        if serializer.is_valid():
            estado_anterior = ticket.estado
            nuevo_estado = serializer.validated_data['estado']
            comentario = serializer.validated_data.get('comentario', '')
            
            if nuevo_estado == 'ENTREGADO':
                puede, mensaje = ticket.puede_entregar()
                if not puede:
                    return Response({'error': mensaje}, status=status.HTTP_400_BAD_REQUEST)
                ticket.marcar_como_entregado()
            else:
                ticket.estado = nuevo_estado
                ticket.save()
            
            EstadoHistorial.objects.create(
                ticket=ticket,
                empresa=ticket.empresa, 
                estado_anterior=estado_anterior,
                estado_nuevo=nuevo_estado,
                creado_por=request.user, 
                comentario=comentario
            )
            
            return Response({
                'status': 'Estado actualizado',
                'estado_anterior': estado_anterior,
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
        if ticket.estado == 'ENTREGADO':
            return Response({'error': 'No se puede cancelar un ticket ya entregado'}, status=status.HTTP_400_BAD_REQUEST)
        
        estado_anterior = ticket.estado
        ticket.estado = 'CANCELADO'
        ticket.save()
        
        EstadoHistorial.objects.create(
            ticket=ticket,
            empresa=ticket.empresa,
            estado_anterior=estado_anterior,
            estado_nuevo='CANCELADO',
            creado_por=request.user,
            comentario=request.data.get('motivo', 'Ticket cancelado')
        )
        return Response({'status': 'Ticket cancelado'})
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        tickets_activos = self.get_queryset()
        
        stats = {
            'total': tickets_activos.count(),
            'recibidos': tickets_activos.filter(estado='RECIBIDO').count(),
            'en_proceso': tickets_activos.filter(estado='EN_PROCESO').count(),
            'listos': tickets_activos.filter(estado='LISTO').count(),
            'entregados_hoy': tickets_activos.filter(estado='ENTREGADO', fecha_entrega__date=timezone.now().date()).count(),
            'urgentes': tickets_activos.filter(prioridad='URGENTE').count(),
            'express': tickets_activos.filter(prioridad='EXPRESS').count(),
        }
        return Response(stats)


class TicketItemViewSet(BaseTenantViewSet):
    queryset = TicketItem.objects.all()
    serializer_class = TicketItemSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        ticket_id = self.request.query_params.get('ticket', None)
        if ticket_id:
            queryset = queryset.filter(ticket_id=ticket_id, ticket__empresa=self.request.user.perfil.empresa)
        return queryset
    
    @action(detail=True, methods=['post'])
    def marcar_completado(self, request, pk=None):
        item = self.get_object() 
        item.completado = True
        item.save()
        return Response({'status': 'Item marcado como completado'})