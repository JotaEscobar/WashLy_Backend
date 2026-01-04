from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from tickets.models import Ticket
from pagos.models import Pago

class DashboardView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        hoy = timezone.now().date()
        mes_actual = timezone.now().replace(day=1).date()
        
        # Tickets de hoy
        tickets_hoy = Ticket.objects.filter(
            fecha_recepcion__date=hoy,
            activo=True
        )
        
        # Tickets del mes
        tickets_mes = Ticket.objects.filter(
            fecha_recepcion__date__gte=mes_actual,
            activo=True
        )
        
        # Ingresos del mes
        ingresos_mes = Pago.objects.filter(
            estado='PAGADO',
            fecha_pago__date__gte=mes_actual
        ).aggregate(total=Sum('monto'))['total'] or 0
        
        stats = {
            'tickets_hoy': {
                'total': tickets_hoy.count(),
                'recibidos': tickets_hoy.filter(estado='RECIBIDO').count(),
                'en_proceso': tickets_hoy.filter(estado='EN_PROCESO').count(),
                'listos': tickets_hoy.filter(estado='LISTO').count(),
                'entregados': tickets_hoy.filter(estado='ENTREGADO').count(),
            },
            'tickets_mes': {
                'total': tickets_mes.count(),
                'entregados': tickets_mes.filter(estado='ENTREGADO').count(),
                'pendientes': tickets_mes.exclude(estado='ENTREGADO').count(),
            },
            'ingresos': {
                'mes_actual': float(ingresos_mes),
            },
            'tickets_urgentes': Ticket.objects.filter(
                prioridad__in=['URGENTE', 'EXPRESS'],
                estado__in=['RECIBIDO', 'EN_PROCESO'],
                activo=True
            ).count()
        }
        
        return Response(stats)

class ReporteVentasView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')
        
        if not fecha_desde or not fecha_hasta:
            return Response({'error': 'Debe proporcionar fecha_desde y fecha_hasta'}, status=400)
        
        pagos = Pago.objects.filter(
            estado='PAGADO',
            fecha_pago__date__gte=fecha_desde,
            fecha_pago__date__lte=fecha_hasta
        )
        
        reporte = {
            'periodo': {
                'desde': fecha_desde,
                'hasta': fecha_hasta
            },
            'total_ingresos': float(pagos.aggregate(total=Sum('monto'))['total'] or 0),
            'total_transacciones': pagos.count(),
            'por_metodo': []
        }
        
        # Agrupar por método de pago
        for metodo, nombre in Pago.METODO_PAGO_CHOICES:
            pagos_metodo = pagos.filter(metodo_pago=metodo)
            if pagos_metodo.exists():
                reporte['por_metodo'].append({
                    'metodo': nombre,
                    'cantidad': pagos_metodo.count(),
                    'total': float(pagos_metodo.aggregate(total=Sum('monto'))['total'] or 0)
                })
        
        return Response(reporte)
