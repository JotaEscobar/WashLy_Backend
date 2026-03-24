"""
Views para la app pagos
Actualizado para SaaS: Filtros por Empresa y Soporte de Métodos Dinámicos
"""

from rest_framework import viewsets, filters, serializers, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, time, timedelta
from decimal import Decimal
import json

from core.permissions import IsActiveSubscription # <--- NUEVO IMPORT
from core.mixins import resolver_sede_desde_request

from .models import Pago, CajaSesion, MovimientoCaja, MetodoPagoConfig
from .serializers import (
    PagoSerializer, CajaSesionSerializer, MovimientoCajaSerializer, 
    MetodoPagoConfigSerializer
)
from core.views import BaseTenantViewSet
from .services import CajaService


class MetodoPagoConfigViewSet(BaseTenantViewSet):
    """CRUD para configurar métodos de pago (Yape, Plin, Bancos)"""
    queryset = MetodoPagoConfig.objects.all().order_by('id')
    serializer_class = MetodoPagoConfigSerializer

    def get_queryset(self):
        # Primero aplicamos el filtro multi-tenant base (por empresa)
        qs = super().get_queryset()
        
        # Solo filtrar por activo en listados (no en detail/update/delete)
        # En el POS solo queremos los activos, pero en Config mostramos todos
        if self.action == 'list':
            incluir_inactivos = self.request.query_params.get('todos') == 'true'
            if not incluir_inactivos:
                qs = qs.filter(activo=True)
            
        return qs

    def perform_create(self, serializer):
        serializer.save(
            empresa=self.request.user.perfil.empresa
        )


class PagoViewSet(BaseTenantViewSet):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_pago', 'ticket__numero_ticket', 'ticket__cliente__nombres', 'ticket__cliente__apellidos']
    ordering = ['-fecha_pago']

    def create(self, request, *args, **kwargs):
        from rest_framework.response import Response
        from rest_framework import serializers
        from pagos.services import registrar_pago
        from tickets.models import Ticket

        user = request.user
        empresa = user.perfil.empresa
        
        monto = request.data.get('monto')
        ticket_id = request.data.get('ticket')
        metodo_pago_id = request.data.get('metodo_pago_config') # ID if sent
        metodo_pago_str = request.data.get('metodo_pago') # fallback o legacy
        referencia = request.data.get('referencia')
        
        ticket = Ticket.objects.filter(id=ticket_id, empresa=empresa).first()
        if not ticket:
            return Response({"error": "Ticket no encontrado"}, status=400)
            
        try:
            pago = registrar_pago(
                user=user,
                empresa=empresa,
                ticket=ticket,
                monto=monto,
                metodo_pago_id=metodo_pago_id,
                metodo_pago_str=metodo_pago_str,
                referencia=referencia
            )
            serializer = self.get_serializer(pago)
            return Response(serializer.data, status=201)
        except serializers.ValidationError as e:
            return Response(e.detail, status=400)

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        pago = self.get_object()
        
        now_local = timezone.localtime(timezone.now())
        pago_local = timezone.localtime(pago.fecha_pago)
        
        if pago_local.date() != now_local.date():
            return Response(
                {'error': 'Solo se pueden extornar pagos realizados el día de hoy.'}, 
                status=400
            )

        if pago.estado == 'ANULADO':
             return Response({'error': 'El pago ya se encuentra anulado.'}, status=400)

        pago.estado = 'ANULADO'
        pago.save()
        
        return Response({'status': 'Pago extornado. El saldo ha retornado al ticket.'})


class CajaViewSet(BaseTenantViewSet):
    queryset = CajaSesion.objects.all().order_by('-fecha_apertura')
    serializer_class = CajaSesionSerializer

    def get_serializer_context(self):
        """Inyecta la sede actual en el contexto del serializer."""
        context = super().get_serializer_context()
        context['sede'] = resolver_sede_desde_request(self.request)
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        
        if fecha_desde:
            dt_start = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            start_aware = timezone.make_aware(datetime.combine(dt_start, time.min))
            queryset = queryset.filter(fecha_apertura__gte=start_aware)
            
        if fecha_hasta:
            dt_end = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            end_aware = timezone.make_aware(datetime.combine(dt_end, time.max))
            queryset = queryset.filter(fecha_apertura__lte=end_aware)
            
        return queryset


    @action(detail=False, methods=['get'])
    def mi_caja(self, request):
        sede = resolver_sede_desde_request(request)
        filters = {
            'usuario': request.user,
            'empresa': request.user.perfil.empresa,
            'estado': 'ABIERTA'
        }
        if sede:
            filters['sede'] = sede
        caja = CajaSesion.objects.filter(**filters).first()
        if caja:
            return Response(self.get_serializer(caja, context={'request': request, 'sede': sede}).data)
        return Response(None)

    @action(detail=False, methods=['get'])
    def ultimo_cierre(self, request):
        sede = resolver_sede_desde_request(request)
        filters = {
            'empresa': request.user.perfil.empresa,
            'estado': 'CERRADA'
        }
        if sede:
            filters['sede'] = sede
        ultima_caja = CajaSesion.objects.filter(**filters).order_by('-fecha_cierre').first()
        
        if not ultima_caja: return Response(None)
        detalle = {}
        try: detalle = json.loads(ultima_caja.detalle_cierre) if ultima_caja.detalle_cierre else {}
        except: detalle = {}
        return Response({'EFECTIVO': detalle.get('EFECTIVO', 0), 'detalle': detalle})

    @action(detail=False, methods=['post'])
    def abrir(self, request):
        empresa = request.user.perfil.empresa
        sede = resolver_sede_desde_request(request)
        
        # Verificar si ya tiene caja abierta en ESTA sede
        filters_check = {'usuario': request.user, 'empresa': empresa, 'estado': 'ABIERTA'}
        if sede:
            filters_check['sede'] = sede
        
        if CajaSesion.objects.filter(**filters_check).exists():
            return Response({'error': 'Ya tienes una caja abierta en esta sede'}, status=400)
        
        detalle = request.data.get('detalle_apertura', {})
        monto_inicial = Decimal(str(request.data.get('monto_inicial', 0)))
        
        caja = CajaSesion.objects.create(
            usuario=request.user,
            empresa=empresa,
            sede=sede,
            monto_inicial=monto_inicial,
            detalle_apertura=json.dumps(detalle) if isinstance(detalle, dict) else str(detalle),
            estado='ABIERTA',
            creado_por=request.user
        )
        serializer = self.get_serializer(caja, context={'request': request, 'sede': sede})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cerrar(self, request, pk=None):
        caja = self.get_object() 
        
        caja.monto_final_real = Decimal(str(request.data.get('monto_real', 0)))
        caja.comentarios = request.data.get('comentarios', '')
        detalle = request.data.get('detalle_cierre', {})
        caja.detalle_cierre = json.dumps(detalle) if isinstance(detalle, dict) else str(detalle)
        
        serializer = self.get_serializer(caja)
        caja.monto_final_sistema = Decimal(str(serializer.data['saldo_actual']))
        caja.diferencia = caja.monto_final_real - caja.monto_final_sistema
        caja.estado = 'CERRADA'
        caja.fecha_cierre = timezone.now()
        caja.save()
        return Response(self.get_serializer(caja).data)

    @action(detail=True, methods=['post'])
    def movimiento(self, request, pk=None):
        caja = self.get_object()
        if caja.estado != 'ABIERTA':
             return Response({'error': 'Caja cerrada'}, status=400)

        metodo_id = request.data.get('metodo_pago_id')
        metodo_config = None
        if metodo_id:
            metodo_config = MetodoPagoConfig.objects.filter(
                id=metodo_id, 
                empresa=caja.empresa
            ).first()

        MovimientoCaja.objects.create(
            caja=caja,
            empresa=caja.empresa, 
            tipo=request.data.get('tipo'),
            monto=request.data.get('monto'),
            metodo_pago_config=metodo_config,
            descripcion=request.data.get('descripcion', ''), 
            categoria=request.data.get('categoria', 'GENERAL'),
            creado_por=request.user
        )
        return Response({'status': 'Movimiento registrado'})

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        caja = self.get_object()
        events = CajaService.build_timeline_events(caja)
        events.sort(key=lambda x: x['hora_raw'] if x['hora_raw'] else timezone.now())
        return Response(events)

    @action(detail=False, methods=['get'])
    def diario(self, request):
        fecha_desde_str = request.query_params.get('fecha_desde')
        fecha_hasta_str = request.query_params.get('fecha_hasta')
        empresa_actual = request.user.perfil.empresa
        sede = resolver_sede_desde_request(request)
        
        now_local = timezone.localtime(timezone.now())
        dt_start = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date() if fecha_desde_str else now_local.date()
        dt_end = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date() if fecha_hasta_str else now_local.date()

        start_aware = timezone.make_aware(datetime.combine(dt_start, time.min))
        end_aware = timezone.make_aware(datetime.combine(dt_end, time.max))

        events = CajaService.get_diario_events(empresa_actual, sede, start_aware, end_aware)
        events.sort(key=lambda x: x['hora_raw'] if x['hora_raw'] else timezone.now())
        return Response(events)