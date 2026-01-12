from rest_framework import viewsets, filters, serializers, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from decimal import Decimal
import json

from .models import Pago, CajaSesion, MovimientoCaja
from .serializers import PagoSerializer, CajaSesionSerializer, MovimientoCajaSerializer

class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_pago', 'ticket__numero_ticket', 'ticket__cliente__nombres', 'ticket__cliente__apellidos']
    ordering = ['-fecha_pago']

    def perform_create(self, serializer):
        user = self.request.user
        caja_abierta = CajaSesion.objects.filter(usuario=user, estado='ABIERTA').first()
        
        if not caja_abierta:
            raise serializers.ValidationError(
                {"error": "No tienes una caja abierta. Apertura caja para registrar pagos."}
            )
            
        serializer.save(creado_por=user, caja=caja_abierta)

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        pago = self.get_object()
        
        if pago.fecha_pago.date() != timezone.now().date():
            return Response(
                {'error': 'Solo se pueden extornar pagos realizados el día de hoy.'}, 
                status=400
            )

        if pago.estado == 'ANULADO':
             return Response({'error': 'El pago ya se encuentra anulado.'}, status=400)

        pago.estado = 'ANULADO'
        pago.save()
        
        return Response({'status': 'Pago extornado. El saldo ha retornado al ticket.'})

class CajaViewSet(viewsets.ModelViewSet):
    queryset = CajaSesion.objects.all().order_by('-fecha_apertura')
    serializer_class = CajaSesionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        
        if fecha_desde:
            queryset = queryset.filter(fecha_apertura__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_apertura__date__lte=fecha_hasta)
            
        return queryset

    # Helper para construir timeline de una caja específica (para cuando se consulta una sesión cerrada antigua)
    def _build_timeline_events(self, caja):
        events = []
        def safe_json(val):
            try: return json.loads(val) if val else {}
            except: return {}

        # 1. Apertura
        events.append({
            'id': f'apertura-{caja.id}',
            'hora_raw': caja.fecha_apertura,
            'tipo_evento': 'APERTURA',
            'fecha': caja.fecha_apertura,
            'monto': caja.monto_inicial,
            'descripcion': f'Apertura de Caja (ID: {caja.id})',
            'usuario': caja.usuario.username,
            'es_entrada': True,
            'estado': 'OK',
            'detalles': safe_json(caja.detalle_apertura) 
        })
        
        # 2. Pagos
        pagos = Pago.objects.filter(caja=caja).select_related('ticket')
        for p in pagos:
            desc = f"Pago Ticket #{p.ticket.numero_ticket}"
            if p.estado == 'ANULADO':
                desc += " (ANULADO)"
            events.append({
                'id': f'pago-{p.id}',
                'hora_raw': p.fecha_pago,
                'tipo_evento': 'VENTA',
                'fecha': p.fecha_pago,
                'monto': p.monto,
                'descripcion': desc,
                'usuario': p.creado_por.username if p.creado_por else 'Sistema',
                'es_entrada': True,
                'estado': p.estado,
                'detalles': {'MÉTODO': p.metodo_pago, 'TICKET': p.ticket.numero_ticket}
            })
            
        # 3. Movimientos
        movimientos = caja.movimientos_extra.all()
        for m in movimientos:
            events.append({
                'id': f'mov-{m.id}',
                'hora_raw': m.creado_en,
                'tipo_evento': m.tipo,
                'fecha': m.creado_en,
                'monto': m.monto,
                'descripcion': f"{m.categoria}: {m.descripcion}", 
                'usuario': m.creado_por.username if m.creado_por else 'Sistema',
                'es_entrada': m.tipo == 'INGRESO',
                'estado': 'OK',
                'detalles': {'CATEGORÍA': m.categoria, 'MÉTODO': m.metodo_pago, 'NOTA': m.descripcion}
            })
            
        # 4. Cierre
        if caja.fecha_cierre and caja.estado == 'CERRADA':
             events.append({
                'id': f'cierre-{caja.id}',
                'hora_raw': caja.fecha_cierre,
                'tipo_evento': 'CIERRE',
                'fecha': caja.fecha_cierre,
                'monto': caja.monto_final_real or 0,
                'descripcion': f'Cierre de Caja (Dif: {caja.diferencia})',
                'usuario': caja.usuario.username,
                'es_entrada': None, 
                'estado': 'OK',
                'detalles': safe_json(caja.detalle_cierre)
            })
        return events

    @action(detail=False, methods=['get'])
    def mi_caja(self, request):
        caja = CajaSesion.objects.filter(usuario=request.user, estado='ABIERTA').first()
        if caja:
            return Response(self.get_serializer(caja).data)
        return Response(None)

    @action(detail=False, methods=['get'])
    def ultimo_cierre(self, request):
        ultima_caja = CajaSesion.objects.filter(estado='CERRADA').order_by('-fecha_cierre').first()
        if not ultima_caja: return Response(None)
        detalle = {}
        try: detalle = json.loads(ultima_caja.detalle_cierre) if ultima_caja.detalle_cierre else {}
        except: detalle = {}
        return Response({'EFECTIVO': detalle.get('EFECTIVO', 0), 'detalle': detalle})

    @action(detail=False, methods=['post'])
    def abrir(self, request):
        if CajaSesion.objects.filter(usuario=request.user, estado='ABIERTA').exists():
            return Response({'error': 'Ya tienes una caja abierta'}, status=400)
        
        detalle = request.data.get('detalle_apertura', {})
        monto_inicial = Decimal(str(request.data.get('monto_inicial', 0)))
        
        caja = CajaSesion.objects.create(
            usuario=request.user,
            monto_inicial=monto_inicial,
            detalle_apertura=json.dumps(detalle) if isinstance(detalle, dict) else str(detalle),
            estado='ABIERTA'
        )
        serializer = self.get_serializer(caja, context={'request': request})
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

        MovimientoCaja.objects.create(
            caja=caja,
            tipo=request.data.get('tipo'),
            monto=request.data.get('monto'),
            metodo_pago=request.data.get('metodo_pago', 'EFECTIVO'),
            descripcion=request.data.get('descripcion', ''), 
            categoria=request.data.get('categoria', 'GENERAL'),
            creado_por=request.user
        )
        return Response({'status': 'Movimiento registrado'})

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        caja = self.get_object()
        events = self._build_timeline_events(caja)
        events.sort(key=lambda x: x['hora_raw'] if x['hora_raw'] else timezone.now())
        return Response(events)

    # --- DIARIO CONSOLIDADO (CORREGIDO) ---
    @action(detail=False, methods=['get'])
    def diario(self, request):
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')
        
        if not fecha_desde: fecha_desde = timezone.localtime(timezone.now()).date()
        if not fecha_hasta: fecha_hasta = timezone.localtime(timezone.now()).date()

        events = []
        def safe_json(val):
            try: return json.loads(val) if val else {}
            except: return {}

        # 1. Pagos por Fecha
        pagos = Pago.objects.filter(
            fecha_pago__date__gte=fecha_desde, 
            fecha_pago__date__lte=fecha_hasta
        ).select_related('ticket', 'creado_por')
        
        for p in pagos:
            desc = f"Pago Ticket #{p.ticket.numero_ticket}"
            if p.estado == 'ANULADO': desc += " (ANULADO)"
            events.append({
                'id': f'pago-{p.id}',
                'hora_raw': p.fecha_pago,
                'tipo_evento': 'VENTA',
                'fecha': p.fecha_pago,
                'monto': p.monto,
                'descripcion': desc,
                'usuario': p.creado_por.username if p.creado_por else 'Sistema',
                'es_entrada': True,
                'estado': p.estado, 
                'detalles': {'MÉTODO': p.metodo_pago, 'TICKET': p.ticket.numero_ticket, 'CLIENTE': str(p.ticket.cliente_info)}
            })

        # 2. Movimientos por Fecha
        movimientos = MovimientoCaja.objects.filter(
            creado_en__date__gte=fecha_desde,
            creado_en__date__lte=fecha_hasta
        ).select_related('creado_por')
        
        for m in movimientos:
            events.append({
                'id': f'mov-{m.id}',
                'hora_raw': m.creado_en,
                'tipo_evento': m.tipo, 
                'fecha': m.creado_en,
                'monto': m.monto,
                'descripcion': f"{m.categoria}: {m.descripcion}", 
                'usuario': m.creado_por.username if m.creado_por else 'Sistema',
                'es_entrada': m.tipo == 'INGRESO',
                'estado': 'OK',
                'detalles': {'CATEGORÍA': m.categoria, 'MÉTODO': m.metodo_pago, 'NOTA': m.descripcion}
            })

        # 3. Aperturas por Fecha
        aperturas = CajaSesion.objects.filter(
            fecha_apertura__date__gte=fecha_desde,
            fecha_apertura__date__lte=fecha_hasta
        ).select_related('usuario')

        for c in aperturas:
            events.append({
                'id': f'apertura-{c.id}',
                'hora_raw': c.fecha_apertura,
                'tipo_evento': 'APERTURA',
                'fecha': c.fecha_apertura,
                'monto': c.monto_inicial,
                'descripcion': f'Apertura de Caja',
                'usuario': c.usuario.username,
                'es_entrada': True,
                'estado': 'OK',
                'detalles': safe_json(c.detalle_apertura) 
            })

        # 4. Cierres por Fecha
        cierres = CajaSesion.objects.filter(
            fecha_cierre__date__gte=fecha_desde,
            fecha_cierre__date__lte=fecha_hasta,
            estado='CERRADA'
        ).select_related('usuario')

        for c in cierres:
             events.append({
                'id': f'cierre-{c.id}',
                'hora_raw': c.fecha_cierre,
                'tipo_evento': 'CIERRE',
                'fecha': c.fecha_cierre,
                'monto': c.monto_final_real or 0,
                'descripcion': f'Cierre de Caja',
                'usuario': c.usuario.username,
                'es_entrada': None, 
                'estado': 'OK',
                'detalles': safe_json(c.detalle_cierre)
            })

        events.sort(key=lambda x: x['hora_raw'] if x['hora_raw'] else timezone.now())
        return Response(events)