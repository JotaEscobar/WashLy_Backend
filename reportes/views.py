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
from pagos.serializers import CajaSesionSerializer  # ✅ Import del serializer
from inventario.models import Producto
from core.mixins import resolver_sede_desde_request

class DashboardKPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'perfil'):
             return Response({'detail': 'Usuario sin perfil asignado'}, status=400)
             
        empresa = request.user.perfil.empresa
        sede = resolver_sede_desde_request(request)
        
        # Filtros base
        filters_pago = {'ticket__empresa': empresa}
        filters_ticket = {'empresa': empresa}
        filters_producto = {'empresa': empresa}

        if sede:
            filters_pago['ticket__sede'] = sede
            filters_ticket['sede'] = sede
            filters_producto['sede'] = sede

        hoy = timezone.localdate()
        
        # 1. CAJA ACTUAL  
        # Caja Sesión ahora es por usuario+sede
        caja_filters = {
            'usuario': request.user, 
            'empresa': empresa,
            'estado': 'ABIERTA'
        }
        if sede:
            caja_filters['sede'] = sede
        caja_sesion = CajaSesion.objects.filter(**caja_filters).first()
        
        saldo_caja = {'total': 0, 'efectivo': 0, 'digital': 0, 'tiene_caja': False} 
        
        if caja_sesion:
            serializer = CajaSesionSerializer(caja_sesion, context={'sede': sede})
            saldo_caja = {
                'tiene_caja': True,
                'total': float(serializer.data['saldo_actual']),
                'efectivo': float(serializer.data['total_efectivo']),
                'digital': float(serializer.data['total_digital'])
            }

        # 2. VENTAS HOY (Pagos pagados hoy)
        ventas_hoy = Pago.objects.filter(
            fecha_pago__date=hoy, 
            estado='PAGADO',
            **filters_pago
        ).aggregate(t=Sum('monto'))['t'] or 0

        # 3. POR COBRAR (Tickets activos confirmados - Lo pagado)
        # Servicios valorizados
        val_servicios = TicketItem.objects.filter(
            ticket__activo=True,
            ticket__estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO', 'ENTREGADO'],
            ticket__empresa=empresa
        )
        
        if sede:
            val_servicios = val_servicios.filter(ticket__sede=sede)
            
        val_servicios = val_servicios.aggregate(t=Sum(F('cantidad') * F('precio_unitario')))['t'] or 0
        
        # Pagos realizados sobre esos tickets
        pagado_tickets = Pago.objects.filter(
            ticket__activo=True,
            ticket__estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO', 'ENTREGADO'],
            estado='PAGADO',
            **filters_pago
        ).aggregate(t=Sum('monto'))['t'] or 0
        
        deuda = max(0, val_servicios - pagado_tickets)

        # 4. CARGA OPERATIVA
        carga = Ticket.objects.filter(
            estado__in=['RECIBIDO', 'EN_PROCESO'], 
            activo=True,
            **filters_ticket
        ).count()

        # 5. ALERTAS
        vencidos = Ticket.objects.filter(
            fecha_prometida__lt=timezone.now(), 
            estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO'], 
            activo=True,
            **filters_ticket
        ).count()
        
        urgentes = Ticket.objects.filter(
            prioridad__in=['URGENTE', 'EXPRESS'], 
            estado__in=['RECIBIDO', 'EN_PROCESO'], 
            activo=True,
            **filters_ticket
        ).count()
        
        # Stock: Filtramos productos activos de la empresa/sede
        stock_bajo = Producto.objects.filter(
            activo=True, 
            stock_actual__lte=F('stock_minimo'),
            **filters_producto
        ).count()

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
        if not hasattr(request.user, 'perfil'):
             return Response({'detail': 'Usuario sin perfil'}, status=400)
             
        empresa = request.user.perfil.empresa
        sede = resolver_sede_desde_request(request)
        
        filters = {'activo': True, 'empresa': empresa}
        if sede:
            filters['sede'] = sede

        conteo = Ticket.objects.filter(**filters).aggregate(
            recibidos=Count('id', filter=Q(estado='RECIBIDO')),
            en_proceso=Count('id', filter=Q(estado='EN_PROCESO')),
            listos=Count('id', filter=Q(estado='LISTO')),
            entregados_hoy=Count('id', filter=Q(estado='ENTREGADO', fecha_entrega__date=timezone.localdate()))
        )
        return Response({'pipeline': conteo})

class DashboardAnaliticaView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not hasattr(request.user, 'perfil'):
             return Response({'detail': 'Usuario sin perfil'}, status=400)

        empresa = request.user.perfil.empresa
        sede = resolver_sede_desde_request(request)
        
        # Filtros
        filters_pago = {'ticket__empresa': empresa}
        filters_ticket = {'empresa': empresa}
        
        if sede:
            filters_pago['ticket__sede'] = sede
            filters_ticket['sede'] = sede

        fecha_fin = timezone.localdate()
        fecha_inicio = fecha_fin - timedelta(days=30)
        
        # Tendencia de Ventas
        ventas = Pago.objects.filter(
            estado='PAGADO', 
            fecha_pago__date__gte=fecha_inicio,
            **filters_pago
        ).annotate(dia=TruncDate('fecha_pago')).values('dia').annotate(total=Sum('monto')).order_by('dia')
        
        datos_ventas = [{'fecha': v['dia'].strftime('%Y-%m-%d'), 'total': float(v['total'])} for v in ventas]
        promedio = sum(d['total'] for d in datos_ventas) / len(datos_ventas) if datos_ventas else 0

        # Top Servicios
        servicios = TicketItem.objects.filter(
            ticket__fecha_recepcion__date__gte=fecha_inicio,
            ticket__empresa=empresa
        )
        if sede:
            servicios = servicios.filter(ticket__sede=sede)
            
        servicios = servicios.values('servicio__nombre').annotate(
            total=Sum(F('cantidad')*F('precio_unitario'))
        ).order_by('-total')[:5]
        
        datos_servicios = [{'name': s['servicio__nombre'], 'value': float(s['total'] or 0)} for s in servicios]

        # Heatmap (Tickets creados)
        tickets_h = Ticket.objects.filter(
            fecha_recepcion__date__gte=fecha_inicio,
            **filters_ticket
        ).annotate(
            d=ExtractWeekDay('fecha_recepcion'), 
            h=ExtractHour('fecha_recepcion')
        ).values('d', 'h').annotate(c=Count('id'))
        
        dias_lbl = ['DOM', 'LUN', 'MAR', 'MIE', 'JUE', 'VIE', 'SAB']
        heatmap = [{'dia': d, 'manana': 0, 'tarde': 0, 'noche': 0} for d in dias_lbl]
        
        for item in tickets_h:
            # Django ExtractWeekDay: 1=Sunday, 7=Saturday
            # Python List index: 0=Sunday ...
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