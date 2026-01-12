from rest_framework import viewsets, filters, serializers
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
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_pago', 'ticket__numero_ticket', 'ticket__cliente__nombres', 'ticket__cliente__apellidos']
    ordering = ['-fecha_pago']

    def perform_create(self, serializer):
        # Validación estricta: No permitir pago sin caja abierta
        user = self.request.user
        caja_abierta = CajaSesion.objects.filter(usuario=user, estado='ABIERTA').first()
        
        if not caja_abierta:
            raise serializers.ValidationError(
                {"error": "No tienes una caja abierta. Apertura caja para registrar pagos."}
            )
            
        # Asignamos la caja automáticamente y el usuario
        serializer.save(creado_por=user, caja=caja_abierta)

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        pago = self.get_object()
        
        # 1. Validar que el pago sea de HOY
        if pago.fecha_pago.date() != timezone.now().date():
            return Response(
                {'error': 'Solo se pueden extornar pagos realizados el día de hoy.'}, 
                status=400
            )

        # 2. Validar que no esté ya anulado
        if pago.estado == 'ANULADO':
             return Response({'error': 'El pago ya se encuentra anulado.'}, status=400)

        # 3. Anulación lógica
        pago.estado = 'ANULADO'
        pago.save()
        
        return Response({'status': 'Pago extornado. El saldo ha retornado al ticket.'})

class CajaViewSet(viewsets.ModelViewSet):
    queryset = CajaSesion.objects.all().order_by('-fecha_apertura')
    serializer_class = CajaSesionSerializer

    @action(detail=False, methods=['get'])
    def mi_caja(self, request):
        """Devuelve la caja ABIERTA del usuario actual"""
        caja = CajaSesion.objects.filter(usuario=request.user, estado='ABIERTA').first()
        if caja:
            return Response(self.get_serializer(caja).data)
        return Response(None)

    @action(detail=False, methods=['get'])
    def ultimo_cierre(self, request):
        """
        Devuelve los saldos finales de la última caja CERRADA globalmente (para continuidad de turnos).
        """
        ultima_caja = CajaSesion.objects.filter(estado='CERRADA').order_by('-fecha_cierre').first()
        
        if not ultima_caja:
            return Response(None) # No hay cierres previos
            
        detalle = {}
        try:
            detalle = json.loads(ultima_caja.detalle_cierre) if ultima_caja.detalle_cierre else {}
        except:
            detalle = {}
            
        return Response({
            'EFECTIVO': ultima_caja.monto_final_real, # Saldo físico declarado
            'detalle': detalle
        })

    @action(detail=False, methods=['post'])
    def abrir(self, request):
        if CajaSesion.objects.filter(usuario=request.user, estado='ABIERTA').exists():
            return Response({'error': 'Ya tienes una caja abierta'}, status=400)
        
        # Obtenemos el detalle de apertura (Efectivo, Tarjeta, etc) si lo envían
        detalle = request.data.get('detalle_apertura', {})
        monto_inicial = Decimal(str(request.data.get('monto_inicial', 0)))
        
        # Guardamos la caja
        caja = CajaSesion.objects.create(
            usuario=request.user,
            monto_inicial=monto_inicial,
            detalle_apertura=json.dumps(detalle) if isinstance(detalle, dict) else str(detalle),
            estado='ABIERTA'
        )
        
        # IMPORTANTE: Usamos el contexto para que el serializer funcione bien si usa 'request'
        serializer = self.get_serializer(caja, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cerrar(self, request, pk=None):
        caja = self.get_object()
        
        monto_input = request.data.get('monto_real', 0)
        caja.monto_final_real = Decimal(str(monto_input)) # Corregido nombre campo model
        caja.comentarios = request.data.get('comentarios', '')
        
        # Detalle de cierre opcional
        detalle_cierre = request.data.get('detalle_cierre', {})
        caja.detalle_cierre = json.dumps(detalle_cierre) if isinstance(detalle_cierre, dict) else str(detalle_cierre)
        
        # Calculamos sistema al momento del cierre
        serializer = self.get_serializer(caja)
        caja.monto_final_sistema = Decimal(str(serializer.data['saldo_actual'])) # Corregido nombre campo model
        
        caja.diferencia = caja.monto_final_real - caja.monto_final_sistema
        caja.estado = 'CERRADA'
        caja.fecha_cierre = timezone.now()
        caja.save()
        
        return Response(self.get_serializer(caja).data)

    @action(detail=True, methods=['post'])
    def movimiento(self, request, pk=None):
        caja = self.get_object()
        
        # Validar que la caja esté abierta para recibir movimientos
        if caja.estado != 'ABIERTA':
             return Response({'error': 'No se pueden agregar movimientos a una caja cerrada'}, status=400)

        MovimientoCaja.objects.create(
            caja=caja,
            tipo=request.data.get('tipo'), # INGRESO / EGRESO
            monto=request.data.get('monto'),
            descripcion=request.data.get('descripcion'),
            categoria=request.data.get('categoria', 'GENERAL'),
            creado_por=request.user
        )
        return Response({'status': 'Movimiento registrado'})

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """
        Retorna el 'Diario Electrónico' de la caja.
        """
        caja = self.get_object()
        events = []

        # 1. Apertura
        events.append({
            'id': f'apertura-{caja.id}',
            'tipo_evento': 'APERTURA',
            'fecha': caja.fecha_apertura,
            'monto': caja.monto_inicial,
            'descripcion': 'Saldo Inicial de Caja',
            'usuario': caja.usuario.username,
            'es_entrada': True,
            'estado': 'OK'
        })
        
        # 2. Pagos (Ventas)
        # Filtramos explícitamente por ID de caja para asegurar consistencia
        pagos = Pago.objects.filter(caja=caja).select_related('ticket')
        for p in pagos:
            events.append({
                'id': f'pago-{p.id}',
                'tipo_evento': 'VENTA',
                'fecha': p.fecha_pago,
                'monto': p.monto,
                'descripcion': f'Cobro Ticket {p.ticket.numero_ticket}',
                'metodo': p.metodo_pago,
                'usuario': p.creado_por.username if p.creado_por else 'Sistema',
                'es_entrada': True,
                'estado': p.estado # 'PAGADO' o 'ANULADO'
            })
            
        # 3. Movimientos (Ingresos/Egresos Manuales)
        movimientos = caja.movimientos_extra.all()
        for m in movimientos:
            events.append({
                'id': f'mov-{m.id}',
                'tipo_evento': m.tipo, # INGRESO / EGRESO
                'fecha': m.creado_en,
                'monto': m.monto,
                'descripcion': f'{m.categoria}: {m.descripcion}',
                'metodo': 'EFECTIVO', 
                'usuario': m.creado_por.username if m.creado_por else 'Sistema',
                'es_entrada': m.tipo == 'INGRESO',
                'estado': 'OK'
            })
            
        # 4. Cierre
        if caja.fecha_cierre and caja.estado == 'CERRADA':
             events.append({
                'id': f'cierre-{caja.id}',
                'tipo_evento': 'CIERRE',
                'fecha': caja.fecha_cierre,
                'monto': caja.monto_final_real or 0,
                'descripcion': f'Cierre de Turno (Diferencia: {caja.diferencia})',
                'usuario': caja.usuario.username,
                'es_entrada': None, 
                'estado': 'OK'
            })

        # Ordenar por fecha, manejando posibles Nones (aunque no debería haber)
        events.sort(key=lambda x: x['fecha'] if x['fecha'] else timezone.now())
        
        return Response(events)