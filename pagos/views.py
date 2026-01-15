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

from .models import Pago, CajaSesion, MovimientoCaja, MetodoPagoConfig
from .serializers import (
    PagoSerializer, CajaSesionSerializer, MovimientoCajaSerializer, 
    MetodoPagoConfigSerializer
)

class BaseTenantViewSet(viewsets.ModelViewSet):
    """
    Clase base para asegurar que todo se filtre por la empresa del usuario.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Filtra siempre por la empresa del usuario logueado
        return self.queryset.model.objects.filter(
            empresa=self.request.user.perfil.empresa
        )
    
    def perform_create(self, serializer):
        # Asigna la empresa automáticamente al crear
        serializer.save(
            empresa=self.request.user.perfil.empresa,
            creado_por=self.request.user
        )


class MetodoPagoConfigViewSet(BaseTenantViewSet):
    """CRUD para configurar métodos de pago (Yape, Plin, Bancos)"""
    queryset = MetodoPagoConfig.objects.filter(activo=True)
    serializer_class = MetodoPagoConfigSerializer


class PagoViewSet(BaseTenantViewSet):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_pago', 'ticket__numero_ticket', 'ticket__cliente__nombres', 'ticket__cliente__apellidos']
    ordering = ['-fecha_pago']

    def perform_create(self, serializer):
        user = self.request.user
        empresa = user.perfil.empresa
        
        # Validar caja abierta EN MI EMPRESA
        caja_abierta = CajaSesion.objects.filter(
            usuario=user, 
            empresa=empresa, 
            estado='ABIERTA'
        ).first()
        
        if not caja_abierta:
            raise serializers.ValidationError(
                {"error": "No tienes una caja abierta. Apertura caja para registrar pagos."}
            )
            
        serializer.save(
            creado_por=user, 
            caja=caja_abierta,
            empresa=empresa
        )

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        pago = self.get_object() # get_object ya usa get_queryset que filtra por empresa
        
        # Validar fecha con timezone local
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

    def get_queryset(self):
        # 1. Filtro base por empresa (del BaseTenantViewSet)
        queryset = super().get_queryset()
        
        # 2. Filtros de fecha adicionales
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
        if 'EFECTIVO' not in apertura_detalle:
            apertura_detalle['EFECTIVO'] = float(caja.monto_inicial)
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
        pagos = Pago.objects.filter(caja=caja).select_related('ticket', 'ticket__cliente', 'metodo_pago_config')
        for p in pagos:
            desc = f"Pago Ticket #{p.ticket.numero_ticket}"
            if p.estado == 'ANULADO':
                desc += " (ANULADO)"
            
            # Nombre del cliente
            cliente_nombre = "N/A"
            if hasattr(p.ticket, 'cliente') and p.ticket.cliente:
                cliente_nombre = f"{p.ticket.cliente.nombres} {p.ticket.cliente.apellidos}".strip()
            
            # Obtener nombre del método dinámico o snapshot
            metodo_nombre = p.metodo_pago_snapshot or (p.metodo_pago_config.nombre_mostrar if p.metodo_pago_config else "N/A")

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
                'detalles': {'MÉTODO': metodo_nombre, 'TICKET': p.ticket.numero_ticket, 'CLIENTE': cliente_nombre}
            })
            
        # 3. Movimientos
        movimientos = caja.movimientos_extra.all().select_related('metodo_pago_config')
        for m in movimientos:
            tipo_texto = "Gasto" if m.tipo == 'EGRESO' else "Ingreso"
            desc = f"{tipo_texto} - {m.categoria}: {m.descripcion}"
            
            # Obtener nombre del método (o EFECTIVO si es null)
            metodo_nombre = m.metodo_pago_config.nombre_mostrar if m.metodo_pago_config else "EFECTIVO"
            
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
                'detalles': {'TIPO': tipo_texto.upper(), 'CATEGORÍA': m.categoria, 'MÉTODO': metodo_nombre, 'NOTA': m.descripcion}
            })
            
        # 4. Cierre
        if caja.fecha_cierre and caja.estado == 'CERRADA':
            cierre_detalle = safe_json(caja.detalle_cierre)
            # Excluir claves internas si es necesario
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
        caja = CajaSesion.objects.filter(
            usuario=request.user, 
            empresa=request.user.perfil.empresa, # Filtro SaaS
            estado='ABIERTA'
        ).first()
        if caja:
            return Response(self.get_serializer(caja).data)
        return Response(None)

    @action(detail=False, methods=['get'])
    def ultimo_cierre(self, request):
        ultima_caja = CajaSesion.objects.filter(
            empresa=request.user.perfil.empresa, # Filtro SaaS
            estado='CERRADA'
        ).order_by('-fecha_cierre').first()
        
        if not ultima_caja: return Response(None)
        detalle = {}
        try: detalle = json.loads(ultima_caja.detalle_cierre) if ultima_caja.detalle_cierre else {}
        except: detalle = {}
        return Response({'EFECTIVO': detalle.get('EFECTIVO', 0), 'detalle': detalle})

    @action(detail=False, methods=['post'])
    def abrir(self, request):
        empresa = request.user.perfil.empresa
        
        if CajaSesion.objects.filter(usuario=request.user, empresa=empresa, estado='ABIERTA').exists():
            return Response({'error': 'Ya tienes una caja abierta'}, status=400)
        
        detalle = request.data.get('detalle_apertura', {})
        monto_inicial = Decimal(str(request.data.get('monto_inicial', 0)))
        
        caja = CajaSesion.objects.create(
            usuario=request.user,
            empresa=empresa, # Asignación SaaS
            monto_inicial=monto_inicial,
            detalle_apertura=json.dumps(detalle) if isinstance(detalle, dict) else str(detalle),
            estado='ABIERTA',
            creado_por=request.user
        )
        serializer = self.get_serializer(caja, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cerrar(self, request, pk=None):
        caja = self.get_object() # Ya filtra por empresa
        
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

        # Buscar config del método de pago si se envía ID
        metodo_id = request.data.get('metodo_pago_id')
        metodo_config = None
        if metodo_id:
            metodo_config = MetodoPagoConfig.objects.filter(
                id=metodo_id, 
                empresa=caja.empresa
            ).first()

        MovimientoCaja.objects.create(
            caja=caja,
            empresa=caja.empresa, # Asignación SaaS
            tipo=request.data.get('tipo'),
            monto=request.data.get('monto'),
            metodo_pago_config=metodo_config, # Asignación dinámica
            # 'metodo_pago' (string antiguo) se puede mantener por compatibilidad o eliminar
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
    # DIARIO CONSOLIDADO - SAAS SAFE
    # =============================================================================
    @action(detail=False, methods=['get'])
    def diario(self, request):
        fecha_desde_str = request.query_params.get('fecha_desde')
        fecha_hasta_str = request.query_params.get('fecha_hasta')
        empresa_actual = request.user.perfil.empresa
        
        # 1. Fechas
        now_local = timezone.localtime(timezone.now())
        dt_start = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date() if fecha_desde_str else now_local.date()
        dt_end = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date() if fecha_hasta_str else now_local.date()

        # 2. Rango Timezone-aware
        start_naive = datetime.combine(dt_start, time.min)
        start_aware = timezone.make_aware(start_naive)
        
        end_naive = datetime.combine(dt_end + timedelta(days=1), time.min) - timedelta(microseconds=1)
        end_aware = timezone.make_aware(end_naive)

        events = []
        
        def safe_json(val):
            try: return json.loads(val) if val else {}
            except: return {}

        print(f"[DIARIO] Buscando movimientos para {empresa_actual} desde {start_aware} hasta {end_aware}")

        # =======================================================================
        # 3. BUSCAR PAGOS (Filtrado por empresa)
        # =======================================================================
        pagos = Pago.objects.filter(
            empresa=empresa_actual,
            fecha_pago__gte=start_aware,
            fecha_pago__lte=end_aware
        ).select_related('ticket', 'creado_por', 'ticket__cliente', 'metodo_pago_config')
        
        for p in pagos:
            desc = f"Pago Ticket #{p.ticket.numero_ticket}"
            if p.estado == 'ANULADO': desc += " (ANULADO)"
            
            cliente_nombre = p.ticket.cliente.nombre_completo if p.ticket.cliente else "N/A"
            metodo_nombre = p.metodo_pago_snapshot or (p.metodo_pago_config.nombre_mostrar if p.metodo_pago_config else "N/A")
            
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
                    'MÉTODO': metodo_nombre,
                    'TICKET': p.ticket.numero_ticket,
                    'CLIENTE': cliente_nombre
                }
            })

        # =======================================================================
        # 4. BUSCAR MOVIMIENTOS MANUALES (Filtrado por empresa)
        # =======================================================================
        movimientos = MovimientoCaja.objects.filter(
            empresa=empresa_actual,
            creado_en__gte=start_aware,
            creado_en__lte=end_aware
        ).select_related('creado_por', 'metodo_pago_config')
        
        for m in movimientos:
            tipo_texto = "Gasto" if m.tipo == 'EGRESO' else "Ingreso"
            desc = f"{tipo_texto} - {m.categoria}: {m.descripcion}"
            metodo_nombre = m.metodo_pago_config.nombre_mostrar if m.metodo_pago_config else "EFECTIVO"
            
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
                    'MÉTODO': metodo_nombre,
                    'NOTA': m.descripcion
                }
            })

        # =======================================================================
        # 5. BUSCAR APERTURAS (Filtrado por empresa)
        # =======================================================================
        aperturas = CajaSesion.objects.filter(
            empresa=empresa_actual,
            fecha_apertura__gte=start_aware,
            fecha_apertura__lte=end_aware
        ).select_related('usuario')

        for c in aperturas:
            apertura_detalle = safe_json(c.detalle_apertura)
            if 'EFECTIVO' not in apertura_detalle:
                apertura_detalle['EFECTIVO'] = float(c.monto_inicial)
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
        # 6. BUSCAR CIERRES (Filtrado por empresa)
        # =======================================================================
        cierres = CajaSesion.objects.filter(
            empresa=empresa_actual,
            fecha_cierre__gte=start_aware,
            fecha_cierre__lte=end_aware,
            estado='CERRADA'
        ).select_related('usuario')

        for c in cierres:
            cierre_detalle = safe_json(c.detalle_cierre)
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
        # 7. ORDENAR Y RETORNAR
        # =======================================================================
        events.sort(key=lambda x: x['hora_raw'] if x['hora_raw'] else timezone.now())
        return Response(events)