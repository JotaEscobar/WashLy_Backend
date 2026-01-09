from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, F, DecimalField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Cliente, Ticket, TicketItem, EstadoHistorial
from .serializers import (
    ClienteSerializer, ClienteListSerializer,
    TicketSerializer, TicketListSerializer, TicketCreateSerializer,
    TicketItemSerializer, EstadoHistorialSerializer, TicketUpdateEstadoSerializer
)

class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.filter(activo=True)
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_documento', 'nombres', 'apellidos', 'telefono', 'email']
    ordering_fields = ['creado_en', 'nombres', 'apellidos']
    ordering = ['-creado_en']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ClienteListSerializer
        return ClienteSerializer
    
    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(actualizado_por=self.request.user)
    
    @action(detail=True, methods=['get'])
    def tickets(self, request, pk=None):
        cliente = self.get_object()
        tickets = cliente.tickets.filter(activo=True)
        serializer = TicketListSerializer(tickets, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def soft_delete(self, request, pk=None):
        cliente = self.get_object()
        cliente.soft_delete()
        return Response({'status': 'Cliente eliminado'})
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        cliente = self.get_object()
        cliente.restore()
        return Response({'status': 'Cliente restaurado'})


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.filter(activo=True).select_related(
        'cliente', 'sede', 'empleado_asignado'
    ).prefetch_related('items', 'historial_estados')
    
    permission_classes = [IsAuthenticated]
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
        queryset = super().get_queryset()
        
        # --- LÓGICA FINANCIERA (Para Módulo de Pagos) ---
        from pagos.models import Pago
        
        # Subquery para obtener el último método de pago (visualización rápida)
        ult_pago = Pago.objects.filter(
            ticket=OuterRef('pk'), 
            estado='PAGADO'
        ).order_by('-fecha_pago')

        queryset = queryset.annotate(
            # Total pagado real (excluyendo anulados)
            total_pagado_db=Coalesce(
                Sum('pagos__monto', filter=Q(pagos__estado='PAGADO')), 
                0, 
                output_field=DecimalField()
            ),
            # Costo total del ticket (Suma de items)
            total_ticket_db=Coalesce(
                Sum(F('items__cantidad') * F('items__precio_unitario')),
                0,
                output_field=DecimalField()
            ),
            # Último método usado
            ultimo_metodo_pago=Subquery(ult_pago.values('metodo_pago')[:1])
        ).distinct() 
        # .distinct() es vital para evitar duplicados al hacer joins con Pagos

        # --- FILTROS ESTÁNDAR ---
        estado = self.request.query_params.get('estado', None)
        if estado:
            queryset = queryset.filter(estado=estado)
        
        prioridad = self.request.query_params.get('prioridad', None)
        if prioridad:
            queryset = queryset.filter(prioridad=prioridad)
        
        cliente_id = self.request.query_params.get('cliente', None)
        if cliente_id:
            queryset = queryset.filter(cliente_id=cliente_id)
        
        fecha_desde = self.request.query_params.get('fecha_desde', None)
        fecha_hasta = self.request.query_params.get('fecha_hasta', None)
        if fecha_desde:
            queryset = queryset.filter(fecha_recepcion__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_recepcion__date__lte=fecha_hasta)
        
        # --- FILTRO DEUDA (Aquí estaba el 'pass' antes) ---
        pendientes_pago = self.request.query_params.get('pendientes_pago', None)
        if pendientes_pago == 'true':
            # Muestra tickets donde (Total Ticket > Total Pagado) Y que no estén cancelados
            queryset = queryset.exclude(estado='CANCELADO').filter(
                total_ticket_db__gt=F('total_pagado_db')
            )
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        # Inyectamos el método de pago en la respuesta JSON sin tocar el Serializer original
        response = super().list(request, *args, **kwargs)
        data_list = response.data['results'] if 'results' in response.data else response.data
        
        # Mapeo eficiente ID -> Metodo
        ticket_map = {t.id: t.ultimo_metodo_pago for t in self.filter_queryset(self.get_queryset())}
        
        for item in data_list:
            item['ultimo_metodo_pago'] = ticket_map.get(item['id'])
            
        return response

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(actualizado_por=self.request.user)
    
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
                estado_anterior=estado_anterior,
                estado_nuevo=nuevo_estado,
                usuario=request.user,
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
            serializer.save(ticket=ticket, creado_por=request.user)
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
            estado_anterior=estado_anterior,
            estado_nuevo='CANCELADO',
            usuario=request.user,
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

class TicketItemViewSet(viewsets.ModelViewSet):
    queryset = TicketItem.objects.all()
    serializer_class = TicketItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        ticket_id = self.request.query_params.get('ticket', None)
        if ticket_id:
            queryset = queryset.filter(ticket_id=ticket_id)
        return queryset
    
    @action(detail=True, methods=['post'])
    def marcar_completado(self, request, pk=None):
        item = self.get_object()
        item.completado = True
        item.save()
        return Response({'status': 'Item marcado como completado'})