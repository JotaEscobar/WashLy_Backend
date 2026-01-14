from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, F, Q, Avg
from django.db.models.functions import TruncDate, Coalesce
from django.utils import timezone
from datetime import timedelta

# Modelos
from tickets.models import Ticket, TicketItem
from pagos.models import Pago, CajaSesion

class DashboardKPIView(APIView):
    """
    Endpoint Nivel 1: Signos Vitales (Carga Inmediata)
    Retorna los 4 números grandes de la cabecera y alertas críticas.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        hoy = timezone.now().date()
        
        # 1. CAJA ACTUAL (Saldo en la sesión abierta del usuario o global)
        # Intentamos buscar la caja abierta del usuario solicitante
        caja_sesion = CajaSesion.objects.filter(
            usuario=request.user, 
            estado='ABIERTA'
        ).first()
        
        saldo_caja_actual = {
            'total': 0,
            'efectivo': 0,
            'digital': 0
        }
        
        if caja_sesion:
            # Calcular pagos en esta sesión
            pagos_sesion = Pago.objects.filter(caja=caja_sesion, estado='PAGADO')
            efectivo = pagos_sesion.filter(metodo_pago='EFECTIVO').aggregate(t=Sum('monto'))['t'] or 0
            # Sumar todos los digitales
            digital = pagos_sesion.exclude(metodo_pago='EFECTIVO').aggregate(t=Sum('monto'))['t'] or 0
            
            # Sumar saldo inicial + ingresos - egresos (Movimientos extra no implementados en detalle aquí, asumimos pagos)
            # Nota: Para mayor precisión en el futuro, sumar MovimientoCaja
            saldo_caja_actual['total'] = caja_sesion.monto_inicial + efectivo # + digital si entra a cuenta bancaria, depende del negocio
            saldo_caja_actual['efectivo'] = float(caja_sesion.monto_inicial + efectivo)
            saldo_caja_actual['digital'] = float(digital)

        # 2. VENTA DEL DÍA (Global)
        ventas_hoy = Pago.objects.filter(
            fecha_pago__date=hoy,
            estado='PAGADO'
        ).aggregate(total=Sum('monto'))['total'] or 0

        # 3. POR COBRAR (Deuda Global de Tickets Activos)
        # Estrategia rápida: Suma total de items de tickets activos - Suma total de pagos de tickets activos
        total_valor_servicios = TicketItem.objects.filter(
            ticket__activo=True,
            ticket__estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO', 'ENTREGADO'] # Excluir cancelados
        ).aggregate(
            total=Sum(F('cantidad') * F('precio_unitario'))
        )['total'] or 0
        
        total_pagado_tickets = Pago.objects.filter(
            ticket__activo=True,
            ticket__estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO', 'ENTREGADO'],
            estado='PAGADO'
        ).aggregate(total=Sum('monto'))['total'] or 0
        
        deuda_total = max(0, total_valor_servicios - total_pagado_tickets)

        # 4. CARGA OPERATIVA (Tickets activos en planta)
        carga_operativa = Ticket.objects.filter(
            estado__in=['RECIBIDO', 'EN_PROCESO'],
            activo=True
        ).count()

        # 5. ALERTAS
        tickets_vencidos_count = Ticket.objects.filter(
            fecha_prometida__lt=timezone.now(),
            estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO'], # No entregados
            activo=True
        ).count()

        urgencias_hoy = Ticket.objects.filter(
            prioridad__in=['URGENTE', 'EXPRESS'],
            estado__in=['RECIBIDO', 'EN_PROCESO'],
            activo=True
        ).count()

        return Response({
            'kpis': {
                'caja_actual': saldo_caja_actual,
                'ventas_hoy': float(ventas_hoy),
                'por_cobrar': float(deuda_total),
                'carga_operativa': carga_operativa
            },
            'alertas': {
                'vencidos': tickets_vencidos_count,
                'urgentes': urgencias_hoy
            }
        })


class DashboardOperativoView(APIView):
    """
    Endpoint Nivel 2: Tablero Operativo (Pipeline)
    Para la gestión visual del flujo de trabajo.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. PIPELINE DE ESTADOS
        # Hacemos una sola query agregada para contar
        conteo_estados = Ticket.objects.filter(activo=True).aggregate(
            recibidos=Count('id', filter=Q(estado='RECIBIDO')),
            en_proceso=Count('id', filter=Q(estado='EN_PROCESO')),
            listos=Count('id', filter=Q(estado='LISTO')),
            entregados_hoy=Count('id', filter=Q(estado='ENTREGADO', fecha_entrega__date=timezone.now().date()))
        )

        # 2. PRÓXIMAS ENTREGAS (Prioridad a los que vencen pronto)
        # Traemos los primeros 10 tickets que NO están entregados ni cancelados
        proximas_entregas_qs = Ticket.objects.filter(
            activo=True
        ).exclude(
            estado__in=['ENTREGADO', 'CANCELADO']
        ).select_related('cliente').order_by('fecha_prometida')[:10]

        lista_entregas = []
        for t in proximas_entregas_qs:
            lista_entregas.append({
                'id': t.id,
                'ticket': t.numero_ticket,
                'cliente': t.cliente.nombre_completo,
                'estado': t.get_estado_display(),
                'prioridad': t.prioridad,
                'fecha_prometida': t.fecha_prometida,
                'vencido': t.fecha_prometida < timezone.now()
            })

        return Response({
            'pipeline': {
                'recibidos': conteo_estados['recibidos'],
                'en_proceso': conteo_estados['en_proceso'],
                'listos': conteo_estados['listos'],
                'entregados_hoy': conteo_estados['entregados_hoy']
            },
            'proximas_entregas': lista_entregas
        })


class DashboardAnaliticaView(APIView):
    """
    Endpoint Nivel 3: Inteligencia de Negocio (Gráficos)
    Carga asíncrona para no bloquear el dashboard principal.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Rango: Últimos 30 días
        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(days=30)

        # 1. TENDENCIA DE VENTAS (Gráfico de Barras/Líneas)
        # Agrupamos pagos por día
        ventas_diarias = Pago.objects.filter(
            estado='PAGADO',
            fecha_pago__date__gte=fecha_inicio,
            fecha_pago__date__lte=fecha_fin
        ).annotate(
            dia=TruncDate('fecha_pago')
        ).values('dia').annotate(
            total=Sum('monto'),
            cantidad=Count('id')
        ).order_by('dia')

        datos_ventas = []
        # Llenar huecos de días sin ventas (opcional, pero recomendado para gráficos lindos)
        # Por simplicidad, enviamos lo que hay. El frontend puede rellenar fechas.
        for v in ventas_diarias:
            datos_ventas.append({
                'fecha': v['dia'].strftime('%Y-%m-%d'),
                'total': float(v['total']),
                'transacciones': v['cantidad']
            })

        # 2. MIX DE SERVICIOS (Pie Chart)
        # Agrupamos items por nombre del servicio
        top_servicios = TicketItem.objects.filter(
            ticket__fecha_recepcion__date__gte=fecha_inicio
        ).values(
            'servicio__nombre'
        ).annotate(
            cantidad_total=Sum('cantidad'),
            ingresos_generados=Sum(F('cantidad') * F('precio_unitario'))
        ).order_by('-ingresos_generados')[:5] # Top 5

        datos_servicios = []
        for s in top_servicios:
            datos_servicios.append({
                'nombre': s['servicio__nombre'],
                'cantidad': float(s['cantidad_total']),
                'total': float(s['ingresos_generados'] or 0)
            })

        return Response({
            'ventas_tendencia': datos_ventas,
            'top_servicios': datos_servicios
        })