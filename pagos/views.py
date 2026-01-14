from rest_framework import viewsets, filters, serializers, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, time, timedelta
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
        
        # Validar fecha con timezone local para evitar errores de UTC
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

class CajaViewSet(viewsets.ModelViewSet):
    queryset = CajaSesion.objects.all().order_by('-fecha_apertura')
    serializer_class = CajaSesionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        
        # Filtrado robusto con Timezone Aware (Perú)
        if fecha_desde:
            dt_start = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            start_aware = timezone.make_aware(datetime.combine(dt_start, time.min))
            queryset = queryset.filter(fecha_apertura__gte=start_aware)
            
        if fecha_hasta:
            dt_end = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            end_aware = timezone.make_aware(datetime.combine(dt_end, time.max))
            queryset = queryset.filter(fecha_apertura__lte=end_aware)
            
        return queryset

    # Helper para construir timeline de una caja específica
    def _build_timeline_events(self, caja):
        events = []
        def safe_json(val):
            try: return json.loads(val) if val else {}
            except: return {}

        # 1. Apertura
        apertura_detalle = safe_json(caja.detalle_apertura)
        # Agregar EFECTIVO al detalle si no está
        if 'EFECTIVO' not in apertura_detalle:
            apertura_detalle['EFECTIVO'] = float(caja.monto_inicial)
        # Agregar comentarios si existen
        if caja.comentarios:
            apertura_detalle['COMENTARIOS'] = caja.comentarios
            
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
            'detalles': apertura_detalle
        })
        
        # 2. Pagos
        pagos = Pago.objects.filter(caja=caja).select_related('ticket', 'ticket__cliente')
        for p in pagos:
            desc = f"Pago Ticket #{p.ticket.numero_ticket}"
            if p.estado == 'ANULADO':
                desc += " (ANULADO)"
            
            # Obtener nombre del cliente
            cliente_nombre = "N/A"
            if hasattr(p.ticket, 'cliente') and p.ticket.cliente:
                cliente_nombre = f"{p.ticket.cliente.nombres} {p.ticket.cliente.apellidos}".strip()
            
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
                'detalles': {'MÉTODO': p.metodo_pago, 'TICKET': p.ticket.numero_ticket, 'CLIENTE': cliente_nombre}
            })
            
        # 3. Movimientos
        movimientos = caja.movimientos_extra.all()
        for m in movimientos:
            # Especificar claramente si es Gasto o Ingreso en la descripción
            tipo_texto = "Gasto" if m.tipo == 'EGRESO' else "Ingreso"
            desc = f"{tipo_texto} - {m.categoria}: {m.descripcion}"
            
            events.append({
                'id': f'mov-{m.id}',
                'hora_raw': m.creado_en,
                'tipo_evento': m.tipo,
                'fecha': m.creado_en,
                'monto': m.monto,
                'descripcion': desc,
                'usuario': m.creado_por.username if m.creado_por else 'Sistema',
                'es_entrada': m.tipo == 'INGRESO',
                'estado': 'OK',
                'detalles': {'TIPO': tipo_texto.upper(), 'CATEGORÍA': m.categoria, 'MÉTODO': m.metodo_pago, 'NOTA': m.descripcion}
            })
            
        # 4. Cierre
        if caja.fecha_cierre and caja.estado == 'CERRADA':
            cierre_detalle = safe_json(caja.detalle_cierre)
            # Excluir TRANSFERENCIA del detalle de cierre
            cierre_detalle_filtrado = {k: v for k, v in cierre_detalle.items() if k != 'TRANSFERENCIA'}
            
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
                'detalles': cierre_detalle_filtrado
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

    # =============================================================================
    # DIARIO CONSOLIDADO - VERSIÓN CORREGIDA PARA WASHLY
    # =============================================================================
    # Problema identificado: El uso de __range con time.max causaba problemas
    # con la zona horaria America/Lima cuando los registros se creaban cerca de
    # la medianoche. Los registros no aparecían porque el timestamp en UTC caía
    # fuera del rango de búsqueda.
    # 
    # Solución implementada:
    # 1. Cambiar de __range a __gte y __lte para mayor control
    # 2. Calcular correctamente el fin del día usando timedelta
    # 3. Agregar logs de debugging para diagnóstico
    # =============================================================================
    
    @action(detail=False, methods=['get'])
    def diario(self, request):
        """
        Endpoint que retorna el historial consolidado de movimientos de caja
        filtrado por rango de fechas. Incluye:
        - Pagos de tickets
        - Movimientos manuales (ingresos/gastos)
        - Aperturas de caja
        - Cierres de caja
        """
        fecha_desde_str = request.query_params.get('fecha_desde')
        fecha_hasta_str = request.query_params.get('fecha_hasta')
        
        # 1. Obtener fecha base en Hora Local (America/Lima)
        now_local = timezone.localtime(timezone.now())
        
        # Determinar rango de fechas (por defecto: hoy)
        if fecha_desde_str:
            dt_start = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
        else:
            dt_start = now_local.date()

        if fecha_hasta_str:
            dt_end = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
        else:
            dt_end = now_local.date()

        # 2. Construir rango timezone-aware correcto
        # IMPORTANTE: No usar time.max (23:59:59.999999) porque causa problemas
        # con la conversión de zonas horarias. En su lugar, usar el inicio del
        # día siguiente menos 1 microsegundo.
        
        # Inicio del día en hora local
        start_naive = datetime.combine(dt_start, time.min)  # 00:00:00
        start_aware = timezone.make_aware(start_naive)
        
        # Fin del día = inicio del día siguiente - 1 microsegundo
        # Esto captura todo hasta las 23:59:59.999999 sin problemas de timezone
        end_naive = datetime.combine(dt_end + timedelta(days=1), time.min) - timedelta(microseconds=1)
        end_aware = timezone.make_aware(end_naive)

        # Lista para almacenar todos los eventos
        events = []
        
        # Helper para parsear JSON de forma segura
        def safe_json(val):
            try: 
                return json.loads(val) if val else {}
            except: 
                return {}

        # DEBUG: Log del rango de búsqueda (útil para diagnóstico)
        # Puedes comentar estas líneas en producción si no las necesitas
        print(f"[DIARIO] Buscando movimientos desde {start_aware} hasta {end_aware}")
        print(f"[DIARIO] Zona horaria: {timezone.get_current_timezone()}")

        # =======================================================================
        # 3. BUSCAR PAGOS DE TICKETS
        # =======================================================================
        # CAMBIO CRÍTICO: Usar __gte y __lte en lugar de __range
        # Esto da mayor control y evita problemas de límites con zonas horarias
        pagos = Pago.objects.filter(
            fecha_pago__gte=start_aware,
            fecha_pago__lte=end_aware
        ).select_related('ticket', 'creado_por', 'ticket__cliente')
        
        print(f"[DIARIO] Pagos encontrados: {pagos.count()}")
        
        for p in pagos:
            desc = f"Pago Ticket #{p.ticket.numero_ticket}"
            if p.estado == 'ANULADO': 
                desc += " (ANULADO)"
            
            # Obtener nombre del cliente
            cliente_nombre = "N/A"
            if hasattr(p.ticket, 'cliente') and p.ticket.cliente:
                cliente_nombre = f"{p.ticket.cliente.nombres} {p.ticket.cliente.apellidos}".strip()
            
            # Construir objeto de evento
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
                'detalles': {
                    'MÉTODO': p.metodo_pago,
                    'TICKET': p.ticket.numero_ticket,
                    'CLIENTE': cliente_nombre
                }
            })

        # =======================================================================
        # 4. BUSCAR MOVIMIENTOS MANUALES (INGRESOS/GASTOS)
        # =======================================================================
        movimientos = MovimientoCaja.objects.filter(
            creado_en__gte=start_aware,
            creado_en__lte=end_aware
        ).select_related('creado_por')
        
        print(f"[DIARIO] Movimientos encontrados: {movimientos.count()}")
        
        for m in movimientos:
            # Especificar claramente si es Gasto o Ingreso en la descripción
            tipo_texto = "Gasto" if m.tipo == 'EGRESO' else "Ingreso"
            desc = f"{tipo_texto} - {m.categoria}: {m.descripcion}"
            
            events.append({
                'id': f'mov-{m.id}',
                'hora_raw': m.creado_en,
                'tipo_evento': m.tipo,
                'fecha': m.creado_en,
                'monto': m.monto,
                'descripcion': desc,
                'usuario': m.creado_por.username if m.creado_por else 'Sistema',
                'es_entrada': m.tipo == 'INGRESO',
                'estado': 'OK',
                'detalles': {
                    'TIPO': tipo_texto.upper(),
                    'CATEGORÍA': m.categoria,
                    'MÉTODO': m.metodo_pago,
                    'NOTA': m.descripcion
                }
            })

        # =======================================================================
        # 5. BUSCAR APERTURAS DE CAJA
        # =======================================================================
        aperturas = CajaSesion.objects.filter(
            fecha_apertura__gte=start_aware,
            fecha_apertura__lte=end_aware
        ).select_related('usuario')

        print(f"[DIARIO] Aperturas encontradas: {aperturas.count()}")

        for c in aperturas:
            apertura_detalle = safe_json(c.detalle_apertura)
            # Agregar EFECTIVO al detalle si no está
            if 'EFECTIVO' not in apertura_detalle:
                apertura_detalle['EFECTIVO'] = float(c.monto_inicial)
            # Agregar comentarios si existen
            if c.comentarios:
                apertura_detalle['COMENTARIOS'] = c.comentarios
                
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
                'detalles': apertura_detalle
            })

        # =======================================================================
        # 6. BUSCAR CIERRES DE CAJA
        # =======================================================================
        cierres = CajaSesion.objects.filter(
            fecha_cierre__gte=start_aware,
            fecha_cierre__lte=end_aware,
            estado='CERRADA'
        ).select_related('usuario')

        print(f"[DIARIO] Cierres encontrados: {cierres.count()}")

        for c in cierres:
            cierre_detalle = safe_json(c.detalle_cierre)
            # Excluir TRANSFERENCIA del detalle de cierre
            cierre_detalle_filtrado = {k: v for k, v in cierre_detalle.items() if k != 'TRANSFERENCIA'}
            
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
                'detalles': cierre_detalle_filtrado
            })

        # =======================================================================
        # 7. ORDENAR EVENTOS POR FECHA Y RETORNAR
        # =======================================================================
        events.sort(key=lambda x: x['hora_raw'] if x['hora_raw'] else timezone.now())
        
        print(f"[DIARIO] Total eventos a retornar: {len(events)}")
        
        return Response(events)
