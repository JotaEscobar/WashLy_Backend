from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import TruncDate, ExtractWeekDay, ExtractHour
from django.utils import timezone
from datetime import timedelta

# Modelos
from tickets.models import Ticket, TicketItem
from pagos.models import Pago, CajaSesion
from inventario.models import Producto

class DashboardKPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        hoy = timezone.now().date()
        
        # 1. CAJA ACTUAL (Desglose exacto)
        caja_sesion = CajaSesion.objects.filter(usuario=request.user, estado='ABIERTA').first()
        saldo_caja = {'total': 0, 'efectivo': 0, 'digital': 0, 'tiene_caja': False}
        
        if caja_sesion:
            saldo_caja['tiene_caja'] = True
            pagos = Pago.objects.filter(caja=caja_sesion, estado='PAGADO')
            movs = caja_sesion.movimientos_extra.all()
            
            # Sumatorias
            v_efec = pagos.filter(metodo_pago='EFECTIVO').aggregate(t=Sum('monto'))['t'] or 0
            v_dig = pagos.exclude(metodo_pago='EFECTIVO').aggregate(t=Sum('monto'))['t'] or 0
            
            i_efec = movs.filter(tipo='INGRESO', metodo_pago='EFECTIVO').aggregate(t=Sum('monto'))['t'] or 0
            i_dig = movs.filter(tipo='INGRESO').exclude(metodo_pago='EFECTIVO').aggregate(t=Sum('monto'))['t'] or 0
            
            e_efec = movs.filter(tipo='EGRESO', metodo_pago='EFECTIVO').aggregate(t=Sum('monto'))['t'] or 0
            e_dig = movs.filter(tipo='EGRESO').exclude(metodo_pago='EFECTIVO').aggregate(t=Sum('monto'))['t'] or 0

            saldo_caja['efectivo'] = float(caja_sesion.monto_inicial + v_efec + i_efec - e_efec)
            saldo_caja['digital'] = float(v_dig + i_dig - e_dig)
            saldo_caja['total'] = saldo_caja['efectivo'] + saldo_caja['digital']

        # 2. VENTAS HOY
        ventas_hoy = Pago.objects.filter(fecha_pago__date=hoy, estado='PAGADO').aggregate(t=Sum('monto'))['t'] or 0

        # 3. POR COBRAR
        val_servicios = TicketItem.objects.filter(
            ticket__activo=True,
            ticket__estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO', 'ENTREGADO']
        ).aggregate(t=Sum(F('cantidad') * F('precio_unitario')))['t'] or 0
        
        pagado_tickets = Pago.objects.filter(
            ticket__activo=True, ticket__estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO', 'ENTREGADO'], estado='PAGADO'
        ).aggregate(t=Sum('monto'))['t'] or 0
        
        deuda = max(0, val_servicios - pagado_tickets)

        # 4. CARGA OPERATIVA
        carga = Ticket.objects.filter(estado__in=['RECIBIDO', 'EN_PROCESO'], activo=True).count()

        # 5. ALERTAS
        vencidos = Ticket.objects.filter(fecha_prometida__lt=timezone.now(), estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO'], activo=True).count()
        urgentes = Ticket.objects.filter(prioridad__in=['URGENTE', 'EXPRESS'], estado__in=['RECIBIDO', 'EN_PROCESO'], activo=True).count()
        stock_bajo = Producto.objects.filter(activo=True, stock_actual__lte=F('stock_minimo')).count()

        return Response({
            'kpis': {
                'caja_actual': saldo_caja,
                'ventas_hoy': float(ventas_hoy),
                'por_cobrar': float(deuda),
                'carga_operativa': carga
            },
            'alertas': {
                'vencidos': vencidos,
                'urgentes': urgentes,
                'stock_bajo': stock_bajo
            }
        })

class DashboardOperativoView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        conteo = Ticket.objects.filter(activo=True).aggregate(
            recibidos=Count('id', filter=Q(estado='RECIBIDO')),
            en_proceso=Count('id', filter=Q(estado='EN_PROCESO')),
            listos=Count('id', filter=Q(estado='LISTO')),
            entregados_hoy=Count('id', filter=Q(estado='ENTREGADO', fecha_entrega__date=timezone.now().date()))
        )
        return Response({'pipeline': conteo})

class DashboardAnaliticaView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(days=30)
        
        # Tendencia
        ventas = Pago.objects.filter(estado='PAGADO', fecha_pago__date__gte=fecha_inicio).annotate(dia=TruncDate('fecha_pago')).values('dia').annotate(total=Sum('monto')).order_by('dia')
        datos_ventas = [{'fecha': v['dia'].strftime('%Y-%m-%d'), 'total': float(v['total'])} for v in ventas]
        promedio = sum(d['total'] for d in datos_ventas) / len(datos_ventas) if datos_ventas else 0

        # Servicios (Nombre claro para leyenda)
        servicios = TicketItem.objects.filter(ticket__fecha_recepcion__date__gte=fecha_inicio).values('servicio__nombre').annotate(total=Sum(F('cantidad')*F('precio_unitario'))).order_by('-total')[:5]
        datos_servicios = [{'name': s['servicio__nombre'], 'value': float(s['total'] or 0)} for s in servicios]

        # Heatmap
        tickets_h = Ticket.objects.filter(fecha_recepcion__date__gte=fecha_inicio).annotate(d=ExtractWeekDay('fecha_recepcion'), h=ExtractHour('fecha_recepcion')).values('d', 'h').annotate(c=Count('id'))
        dias_lbl = ['DOM', 'LUN', 'MAR', 'MIE', 'JUE', 'VIE', 'SAB']
        heatmap = [{'dia': d, 'manana': 0, 'tarde': 0, 'noche': 0} for d in dias_lbl]
        
        for item in tickets_h:
            idx = item['d'] - 1 
            if 0 <= idx <= 6:
                h, c = item['h'], item['c']
                if 6 <= h < 12: heatmap[idx]['manana'] += c
                elif 12 <= h < 18: heatmap[idx]['tarde'] += c
                elif 18 <= h <= 23: heatmap[idx]['noche'] += c

        return Response({
            'ventas_tendencia': datos_ventas,
            'promedio_ventas': promedio,
            'top_servicios': datos_servicios,
            'horas_pico': heatmap
        })