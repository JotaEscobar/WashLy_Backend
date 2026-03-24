from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import TruncDate, ExtractWeekDay, ExtractHour
from django.utils import timezone
from datetime import timedelta
import datetime

from django.template.loader import render_to_string
from django.http import HttpResponse
import os
import base64
from django.conf import settings
try:
    import weasyprint
except Exception:
    weasyprint = None  # Weasyprint requires GTK3 libraries natively installed on Windows


# Modelos
from tickets.models import Ticket, TicketItem, Cliente
from pagos.models import Pago, CajaSesion
from pagos.serializers import CajaSesionSerializer
from inventario.models import Producto
from core.mixins import resolver_sede_desde_request

from .services import DashboardService

class DashboardKPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'perfil'):
             return Response({'detail': 'Usuario sin perfil asignado'}, status=400)
             
        empresa = request.user.perfil.empresa
        sede = resolver_sede_desde_request(request)
        
        # Delegamos a DashboardService
        data = DashboardService.get_kpis(request.user, empresa, sede)
        return Response(data)

class DashboardOperativoView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not hasattr(request.user, 'perfil'):
             return Response({'detail': 'Usuario sin perfil'}, status=400)
             
        empresa = request.user.perfil.empresa
        sede = resolver_sede_desde_request(request)
        
        # Delegamos a DashboardService
        data = DashboardService.get_operativo(empresa, sede)
        return Response(data)

class DashboardAnaliticaView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not hasattr(request.user, 'perfil'):
             return Response({'detail': 'Usuario sin perfil'}, status=400)

        empresa = request.user.perfil.empresa
        sede = resolver_sede_desde_request(request)
        
        # Delegamos a DashboardService
        data = DashboardService.get_analitica(empresa, sede)
        return Response(data)


from django.utils.dateparse import parse_date
from datetime import datetime, time


import datetime as dt

class ReportePDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'perfil'):
             return HttpResponse('Usuario sin perfil asignado', status=400)
             
        empresa = request.user.perfil.empresa
        sede_id = request.query_params.get('sede_id')
        if sede_id and sede_id != 'todas':
            from core.models import Sede
            sede = Sede.objects.filter(id=sede_id, empresa=empresa).first()
        else:
            sede = resolver_sede_desde_request(request)
            
        modulo = request.query_params.get('modulo', 'TICKETS')
        inicio_str = request.query_params.get('inicio')
        fin_str = request.query_params.get('fin')
        estado = request.query_params.get('estado', 'TODOS')
        
        # Nuevos parámetros de filtros
        metodo_pago = request.query_params.get('metodo_pago', 'TODOS')
        categoria_servicio = request.query_params.get('categoria_servicio', 'TODOS')
        alerta_stock = request.query_params.get('alerta_stock', 'TODOS')
        categoria_producto = request.query_params.get('categoria_producto', 'TODOS')
        estado_deuda = request.query_params.get('estado_deuda', 'TODOS')
        nivel_fidelizacion = request.query_params.get('nivel_fidelizacion', 'TODOS')
        
        # Parse Dates 
        inicio_dt = None
        fin_dt = None
        inicio_date = None
        fin_date = None
        if inicio_str and fin_str:
            inicio_date = parse_date(inicio_str)
            fin_date = parse_date(fin_str)
            if inicio_date and fin_date:
                # timezone-aware start and end 
                inicio_dt = timezone.make_aware(dt.datetime.combine(inicio_date, dt.time.min))
                fin_dt = timezone.make_aware(dt.datetime.combine(fin_date, dt.time.max))

        context = {
            'empresa': empresa,
            'emisor': request.user.get_full_name() or request.user.username,
            'fecha_impresion': timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M'),
            'rango_fechas': f"{inicio_str} al {fin_str}" if inicio_str and fin_str else "Histórico Completo",
            'registros': []
        }
        
        # Base64 embedding logic for WeasyPrint
        logo_path = os.path.join(settings.BASE_DIR, 'reportes', 'static', 'img', 'logo-whasly.png')
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
                context['logo_b64'] = f"data:image/png;base64,{encoded_string}"
        else:
            context['logo_b64'] = ""

        template_name = 'reportes/base_reporte.html'
        
        from .services import ReporteService
        
        if modulo == 'TICKETS':
            template_name = 'reportes/tickets.html'
            data = ReporteService.get_tickets_data(empresa, sede, inicio_dt, fin_dt, estado)
            context.update(data)

        elif modulo == 'CAJA_PAGOS':
            template_name = 'reportes/caja_pagos.html'
            data = ReporteService.get_caja_pagos_data(empresa, sede, inicio_dt, fin_dt, estado, metodo_pago)
            context.update(data)
            
        elif modulo == 'DIARIO_ELECTRONICO':
            template_name = 'reportes/diario_electronico.html'
            data = ReporteService.get_diario_electronico_data(empresa, sede, inicio_dt, fin_dt)
            context.update(data)
            
        elif modulo == 'VENTAS':
            template_name = 'reportes/ventas.html'
            data = ReporteService.get_ventas_data(empresa, sede, inicio_dt, fin_dt, categoria_servicio)
            context.update(data)
            
        elif modulo == 'INVENTARIO':
            template_name = 'reportes/inventario.html'
            data = ReporteService.get_inventario_data(empresa, sede, categoria_producto, alerta_stock)
            context.update(data)

        elif modulo == 'CLIENTES':
            template_name = 'reportes/clientes.html'
            data = ReporteService.get_clientes_data(empresa, sede, inicio_date, fin_date, nivel_fidelizacion, estado_deuda)
            context.update(data)

        # 4. Renderizar HTML
        html_string = render_to_string(template_name, context)

        # 5. Generar PDF (o devolver HTML para impresión en navegador)
        filename_base = f"Reporte_{modulo}_{timezone.now().strftime('%Y%m%d_%H%M')}"
        if weasyprint:
            pdf_file = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename_base}.pdf"'
            return response
        else:
            # Fallback a HTML Puro que acciona window.print() (Ideal para dev local Windows)
            html_string_with_print = html_string.replace('</body>', '<script>window.onload = function() { window.print(); }</script></body>')
            response = HttpResponse(html_string_with_print, content_type='text/html')
            # Forcing inline disposition so it opens in the browser directly instead of downloading
            response['Content-Disposition'] = 'inline'
            return response