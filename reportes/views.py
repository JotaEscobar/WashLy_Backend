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

        # Placeholder for the CLIENTES query mapping, assuming it belongs to a different view/context
        # If this was intended for a report generation view, it would look something like this:
        # if modulo == 'CLIENTES':
        #    qs = Cliente.objects.filter(empresa=empresa)
        #    context['registros'] = qs.order_by('nombre')
        #    context['total_clientes'] = qs.count()
        #    template_name = 'reportes/clientes.html'

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

from django.utils.dateparse import parse_date
from datetime import datetime, time

from django.utils.dateparse import parse_date
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
        
        if modulo == 'TICKETS':
            template_name = 'reportes/tickets.html'
            qs = Ticket.objects.filter(empresa=empresa, activo=True)
            if sede: qs = qs.filter(sede=sede)
            if inicio_dt and fin_dt: qs = qs.filter(fecha_recepcion__range=[inicio_dt, fin_dt])
            if estado and estado != 'TODOS': qs = qs.filter(estado=estado)
            qs = qs.select_related('cliente').order_by('-fecha_recepcion')
            
            context['registros'] = qs
            context['total_tickets'] = qs.count()
            # Django requires the ticket to have a raw total, or we calculate it. 
            # In the template they expect `t.total`, but get_total() is a method.
            # We will annotate or evaluate it in the view if needed.
            # For simplicity, we'll pass the queryset. The template uses t.total, assuming it's a field or property.
            # If `total` is a method `calcular_total()`, the template in Django needs a property `total`.
            # Let's dynamically add it to avoiding breaking the template.
            tickets_list = []
            total_generado = 0
            for t in qs:
                tot = t.calcular_total()
                total_generado += tot
                # Create a proxy dict to pass to template
                tickets_list.append({
                    'id': t.numero_ticket,
                    'fecha_recepcion': t.fecha_recepcion,
                    'cliente': {'nombre': t.cliente.nombre_completo if t.cliente else 'Sin Cliente'},
                    'estado': t.estado,
                    'total': tot
                })
            context['registros'] = tickets_list
            context['total_generado'] = total_generado

        elif modulo == 'CAJA_PAGOS':
            template_name = 'reportes/caja_pagos.html'
            qs = Pago.objects.filter(ticket__empresa=empresa)
            if estado == 'PAGADO':
                qs = qs.filter(estado='PAGADO')
            elif estado == 'PENDIENTE':
                qs = qs.filter(estado='PENDIENTE')
            
            if metodo_pago and metodo_pago != 'TODOS':
                qs = qs.filter(metodo_pago_config_id=metodo_pago)

            if sede: qs = qs.filter(ticket__sede=sede)
            if inicio_dt and fin_dt: qs = qs.filter(fecha_pago__range=[inicio_dt, fin_dt])
            qs = qs.select_related('ticket', 'ticket__cliente', 'metodo_pago_config').order_by('-fecha_pago')
            
            pagos_list = []
            total_ingresos = 0
            for p in qs:
                tot = p.monto
                total_ingresos += tot
                pagos_list.append({
                    'id': p.id,
                    'fecha': p.fecha_pago,
                    'cliente': p.ticket.cliente.nombre_completo if p.ticket.cliente else 'N/A',
                    'metodo': getattr(p.metodo_pago_config, 'nombre_mostrar', p.metodo_pago_snapshot) if p.metodo_pago_config else p.metodo_pago_snapshot,
                    'monto': tot,
                    'estado': p.estado
                })
            context['registros'] = pagos_list
            context['ingresos'] = total_ingresos
            
        elif modulo == 'DIARIO_ELECTRONICO':
            template_name = 'reportes/diario_electronico.html'
            from pagos.models import MovimientoCaja
            qs_pagos = Pago.objects.filter(ticket__empresa=empresa, estado='PAGADO')
            qs_movs = MovimientoCaja.objects.filter(caja__empresa=empresa)
            
            if sede: 
                qs_pagos = qs_pagos.filter(ticket__sede=sede)
                qs_movs = qs_movs.filter(caja__sede=sede)
            if inicio_dt and fin_dt: 
                qs_pagos = qs_pagos.filter(fecha_pago__range=[inicio_dt, fin_dt])
                qs_movs = qs_movs.filter(creado_en__range=[inicio_dt, fin_dt])
                
            transacciones = []
            total_ingresos = 0
            total_egresos = 0
            
            for p in qs_pagos:
                transacciones.append({
                    'fecha': p.fecha_pago,
                    'tipo': 'INGRESO',
                    'concepto': f'Referencia TKT: {p.ticket.numero_ticket}',
                    'cliente': p.ticket.cliente.nombre_completo if p.ticket.cliente else '-',
                    'metodo': getattr(p.metodo_pago_config, 'nombre_mostrar', p.metodo_pago_snapshot) if p.metodo_pago_config else p.metodo_pago_snapshot,
                    'monto': p.monto,
                    'usuario': p.creado_por.username if p.creado_por else '-'
                })
                total_ingresos += p.monto
                
            for m in qs_movs:
                transacciones.append({
                    'fecha': m.creado_en,
                    'tipo': m.tipo,
                    'concepto': m.descripcion,
                    'cliente': '-',
                    'metodo': getattr(m.metodo_pago_config, 'nombre_mostrar', 'Efectivo') if m.metodo_pago_config else 'General',
                    'monto': m.monto,
                    'usuario': m.creado_por.username if m.creado_por else '-'
                })
                if m.tipo == 'INGRESO':
                    total_ingresos += m.monto
                else:
                    total_egresos += m.monto
            
            # Sort by date
            transacciones.sort(key=lambda x: x['fecha'])
            context['transacciones'] = transacciones
            context['total_ingresos'] = total_ingresos
            context['total_egresos'] = total_egresos
            context['saldo_neto'] = total_ingresos - total_egresos
            
        elif modulo == 'VENTAS':
            template_name = 'reportes/ventas.html'
            qs = TicketItem.objects.filter(ticket__empresa=empresa, ticket__activo=True)
            if sede: qs = qs.filter(ticket__sede=sede)
            if inicio_dt and fin_dt: qs = qs.filter(ticket__fecha_recepcion__range=[inicio_dt, fin_dt])
            if categoria_servicio and categoria_servicio != 'TODOS':
                qs = qs.filter(servicio__categoria_id=categoria_servicio)
                
            qs = qs.values('servicio__nombre').annotate(
                cantidad_total=Sum('cantidad'),
                subtotal=Sum(F('cantidad') * F('precio_unitario'))
            ).order_by('-subtotal')
            
            total_ventas = sum(item['subtotal'] for item in qs if item['subtotal'])
            context['registros'] = qs
            context['total_ventas'] = total_ventas
            
        elif modulo == 'INVENTARIO':
            template_name = 'reportes/inventario.html'
            qs = Producto.objects.filter(empresa=empresa, activo=True)
            if sede: qs = qs.filter(sede=sede)
            
            if categoria_producto and categoria_producto != 'TODOS':
                qs = qs.filter(categoria_id=categoria_producto)
                
            if alerta_stock == 'BAJO':
                qs = qs.filter(stock_actual__lte=F('stock_minimo'), stock_actual__gt=0)
            elif alerta_stock == 'AGOTADO':
                qs = qs.filter(stock_actual__lte=0)
                
            context['registros'] = qs

        elif modulo == 'CLIENTES':
            template_name = 'reportes/clientes.html'
            qs = Cliente.objects.filter(empresa=empresa)
            if inicio_date and fin_date:
                qs = qs.filter(fecha_registro__range=[inicio_date, fin_date])
            if sede: qs = qs.filter(sede=sede)
            
            if nivel_fidelizacion == 'NUEVO':
                thirty_days_ago = timezone.now() - timedelta(days=30)
                qs = qs.filter(creado_en__gte=thirty_days_ago)
            elif nivel_fidelizacion == 'VIP':
                qs = qs.annotate(
                    total_gastado_qs=Sum('tickets__pagos__monto', filter=Q(tickets__pagos__estado='PAGADO'))
                ).filter(total_gastado_qs__gte=200) # Configuramos 200 como umbral temporal
                
            # Evaluacion en memoria para estado_deuda (Deudores)
            clientes_finales = []
            if estado_deuda == 'DEUDORES':
                for c in qs:
                    saldos = Ticket.objects.filter(cliente=c, empresa=empresa, estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO']).exclude(estado='ANULADO').exclude(activo=False)
                    debt = sum(t.calcular_saldo_pendiente() for t in saldos)
                    if debt > 0:
                        c.saldo_pendiente_total = debt
                        clientes_finales.append(c)
                qs = clientes_finales
            else:
                for c in qs:
                    c.saldo_pendiente_total = 0
            
            context['registros'] = qs

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