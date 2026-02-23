from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.db.models import Count, Sum
from core.models import Empresa, HistorialSuscripcion
from django.utils import timezone
from datetime import timedelta

class SuperAdminStatsView(APIView):
    """
    Estadísticas globales para el dueño del sistema (Métricas SaaS).
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_empresas = Empresa.objects.count()
        empresas_activas = Empresa.objects.filter(estado='ACTIVO').count()
        empresas_demos = Empresa.objects.filter(plan='DEMO').count()
        empresas_mensual = Empresa.objects.filter(plan='MENSUAL').count()
        
        # Suscripciones por vencer en los próximos 7 días
        vencen_pronto = Empresa.objects.filter(
            fecha_vencimiento__lte=timezone.now() + timedelta(days=7),
            fecha_vencimiento__gte=timezone.now(),
            estado='ACTIVO'
        ).count()

        # Ingresos del mes (MRR estimado basado en el último mes de historial)
        mes_actual = timezone.now().month
        anio_actual = timezone.now().year
        ingresos_mes = HistorialSuscripcion.objects.filter(
            fecha_pago__month=mes_actual,
            fecha_pago__year=anio_actual
        ).aggregate(total=Sum('monto'))['total'] or 0

        return Response({
            'resumen': {
                'total_empresas': total_empresas,
                'activas': empresas_activas,
                'demos': empresas_demos,
                'mensuales': empresas_mensual,
                'por_vencer': vencen_pronto
            },
            'financiero': {
                'ingresos_mes_actual': float(ingresos_mes)
            }
        })

class GlobalEmpresasView(APIView):
    """
    Listado y gestión rápida de empresas.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        empresas = Empresa.objects.all().order_by('-fecha_inicio')
        data = []
        for e in empresas:
            dias_restantes = (e.fecha_vencimiento - timezone.now()).days
            data.append({
                'id': e.id,
                'nombre': e.nombre,
                'ruc': e.ruc,
                'plan': e.plan,
                'estado': e.estado,
                'fecha_vencimiento': e.fecha_vencimiento.strftime('%Y-%m-%d'),
                'dias_restantes': dias_restantes,
                'email': e.email_contacto
            })
        return Response(data)

class AccionesEmpresaView(APIView):
    """
    Acciones rápidas como extender demo o suspender.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            empresa = Empresa.objects.get(pk=pk)
            accion = request.data.get('accion')

            if accion == 'EXTENDER_DEMO':
                # Añadir 7 días más a la fecha de vencimiento
                empresa.fecha_vencimiento += timedelta(days=7)
                empresa.save()
                return Response({'status': 'Demo extendido 7 días'})

            elif accion == 'SUSPENDER':
                empresa.estado = 'SUSPENDIDO'
                empresa.save()
                return Response({'status': 'Empresa suspendida'})

            elif accion == 'ACTIVAR':
                empresa.estado = 'ACTIVO'
                empresa.save()
                return Response({'status': 'Empresa reactivada'})

            return Response({'error': 'Acción no válida'}, status=400)
        except Empresa.DoesNotExist:
            return Response({'error': 'Empresa no encontrada'}, status=404)
