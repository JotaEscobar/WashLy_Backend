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

    @action(detail=False, methods=['get'])
    def mi_caja(self, request):
        caja = CajaSesion.objects.filter(usuario=request.user, estado='ABIERTA').first()
        if caja:
            return Response(self.get_serializer(caja).data)
        return Response(None)

    @action(detail=False, methods=['get'])
    def ultimo_cierre(self, request):
        ultima_caja = CajaSesion.objects.filter(estado='CERRADA').order_by('-fecha_cierre').first()
        
        if not ultima_caja:
            return Response(None)
            
        detalle = {}
        try:
            detalle = json.loads(ultima_caja.detalle_cierre) if ultima_caja.detalle_cierre else {}
        except:
            detalle = {}
        
        efectivo_real = detalle.get('EFECTIVO', 0)
            
        return Response({
            'EFECTIVO': efectivo_real,
            'detalle': detalle
        })

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
        
        monto_input = request.data.get('monto_real', 0)
        caja.monto_final_real = Decimal(str(monto_input))
        caja.comentarios = request.data.get('comentarios', '')
        
        detalle_cierre = request.data.get('detalle_cierre', {})
        caja.detalle_cierre = json.dumps(detalle_cierre) if isinstance(detalle_cierre, dict) else str(detalle_cierre)
        
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
             return Response({'error': 'No se pueden agregar movimientos a una caja cerrada'}, status=400)

        # Capturamos datos extendidos
        descripcion_raw = request.data.get('descripcion', '')
        metodo_pago = request.data.get('metodo_pago', 'EFECTIVO')
        
        # Guardamos el metodo en la descripción para persistencia simple si el modelo no tiene el campo
        # (Esto asegura compatibilidad sin migraciones complejas inmediatas)
        descripcion_final = f"{descripcion_raw} | Método: {metodo_pago}"

        MovimientoCaja.objects.create(
            caja=caja,
            tipo=request.data.get('tipo'),
            monto=request.data.get('monto'),
            descripcion=descripcion_final, 
            categoria=request.data.get('categoria', 'GENERAL'),
            creado_por=request.user
        )
        return Response({'status': 'Movimiento registrado'})

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        caja = self.get_object()
        events = []

        # Helper para parsear JSON seguro
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
            'descripcion': 'Saldo Inicial de Caja',
            'usuario': caja.usuario.username,
            'es_entrada': True,
            'estado': 'OK',
            'detalles': safe_json(caja.detalle_apertura) # Para el modal del ojo
        })
        
        # 2. Pagos (Ventas)
        pagos = Pago.objects.filter(caja=caja).select_related('ticket')
        for p in pagos:
            events.append({
                'id': f'pago-{p.id}',
                'hora_raw': p.fecha_pago,
                'tipo_evento': 'VENTA',
                'fecha': p.fecha_pago,
                'monto': p.monto,
                'descripcion': f'Ticket #{p.ticket.numero_ticket}',
                'metodo': p.metodo_pago,
                'usuario': p.creado_por.username if p.creado_por else 'Sistema',
                'es_entrada': True,
                'estado': p.estado,
                'detalles': {'MÉTODO': p.metodo_pago, 'TICKET': p.ticket.numero_ticket, 'CLIENTE': str(p.ticket.cliente_info)}
            })
            
        # 3. Movimientos (Ingresos/Gastos)
        movimientos = caja.movimientos_extra.all()
        for m in movimientos:
            # Intentamos extraer el metodo de la descripción si fue guardado con el formato nuevo
            desc_parts = m.descripcion.split('| Método:')
            texto_desc = desc_parts[0].strip()
            metodo_desc = desc_parts[1].strip() if len(desc_parts) > 1 else 'EFECTIVO'

            events.append({
                'id': f'mov-{m.id}',
                'hora_raw': m.creado_en,
                'tipo_evento': m.tipo, # INGRESO o EGRESO
                'fecha': m.creado_en,
                'monto': m.monto,
                'descripcion': f"{m.categoria}: {texto_desc}", 
                'usuario': m.creado_por.username if m.creado_por else 'Sistema',
                'es_entrada': m.tipo == 'INGRESO',
                'estado': 'OK',
                'detalles': {'CATEGORÍA': m.categoria, 'MÉTODO': metodo_desc, 'NOTA': texto_desc}
            })
            
        # 4. Cierre
        if caja.fecha_cierre and caja.estado == 'CERRADA':
             events.append({
                'id': f'cierre-{caja.id}',
                'hora_raw': caja.fecha_cierre,
                'tipo_evento': 'CIERRE',
                'fecha': caja.fecha_cierre,
                'monto': caja.monto_final_real or 0,
                'descripcion': f'Arqueo Final (Dif: {caja.diferencia})',
                'usuario': caja.usuario.username,
                'es_entrada': None, 
                'estado': 'OK',
                'detalles': safe_json(caja.detalle_cierre)
            })

        # Ordenar cronológicamente
        events.sort(key=lambda x: x['hora_raw'] if x['hora_raw'] else timezone.now())
        
        return Response(events)