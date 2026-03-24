from django.db.models import Sum, Count, F, Q
from django.db.models.functions import TruncDate, ExtractWeekDay, ExtractHour
from django.utils import timezone
from datetime import timedelta
from tickets.models import Ticket, TicketItem, Cliente
from pagos.models import Pago, CajaSesion
from inventario.models import Producto

class DashboardService:
    @staticmethod
    def get_kpis(user, empresa, sede=None):
        hoy = timezone.localdate()
        
        # 1. Caja Actual
        caja_filters = {'usuario': user, 'empresa': empresa, 'estado': 'ABIERTA'}
        if sede: caja_filters['sede'] = sede
        caja_sesion = CajaSesion.objects.filter(**caja_filters).first()
        
        saldo_caja = {'total': 0, 'efectivo': 0, 'digital': 0, 'tiene_caja': False}
        if caja_sesion:
            from pagos.serializers import CajaSesionSerializer
            serializer = CajaSesionSerializer(caja_sesion, context={'sede': sede})
            saldo_caja = {
                'tiene_caja': True,
                'total': float(serializer.data['saldo_actual']),
                'efectivo': float(serializer.data['total_efectivo']),
                'digital': float(serializer.data['total_digital'])
            }

        # 2. Ventas Hoy
        filters_pago = {'ticket__empresa': empresa, 'estado': 'PAGADO', 'fecha_pago__date': hoy}
        if sede: filters_pago['ticket__sede'] = sede
        ventas_hoy = Pago.objects.filter(**filters_pago).aggregate(t=Sum('monto'))['t'] or 0

        # 3. Por Cobrar
        val_servicios_qs = TicketItem.objects.filter(
            ticket__activo=True,
            ticket__estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO', 'ENTREGADO'],
            ticket__empresa=empresa
        )
        if sede: val_servicios_qs = val_servicios_qs.filter(ticket__sede=sede)
        val_servicios = val_servicios_qs.aggregate(t=Sum(F('cantidad') * F('precio_unitario')))['t'] or 0
        
        pagado_tickets_qs = Pago.objects.filter(
            ticket__activo=True,
            ticket__estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO', 'ENTREGADO'],
            ticket__empresa=empresa,
            estado='PAGADO'
        )
        if sede: pagado_tickets_qs = pagado_tickets_qs.filter(ticket__sede=sede)
        pagado_tickets = pagado_tickets_qs.aggregate(t=Sum('monto'))['t'] or 0
        deuda = max(0, val_servicios - pagado_tickets)

        # 4. Carga Operativa & Alertas
        filters_tkt = {'empresa': empresa, 'activo': True}
        if sede: filters_tkt['sede'] = sede
        
        carga = Ticket.objects.filter(estado__in=['RECIBIDO', 'EN_PROCESO'], **filters_tkt).count()
        vencidos = Ticket.objects.filter(fecha_prometida__lt=timezone.now(), estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO'], **filters_tkt).count()
        urgentes = Ticket.objects.filter(prioridad__in=['URGENTE', 'EXPRESS'], estado__in=['RECIBIDO', 'EN_PROCESO'], **filters_tkt).count()
        
        # Stock
        filters_prod = {'empresa': empresa, 'activo': True, 'stock_actual__lte': F('stock_minimo')}
        if sede: filters_prod['sede'] = sede
        stock_bajo = Producto.objects.filter(**filters_prod).count()

        return {
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
        }

    @staticmethod
    def get_analitica(empresa, sede=None):
        fecha_fin = timezone.localdate()
        fecha_inicio = fecha_fin - timedelta(days=30)
        
        filters_pago = {'ticket__empresa': empresa, 'estado': 'PAGADO', 'fecha_pago__date__gte': fecha_inicio}
        if sede: filters_pago['ticket__sede'] = sede
        
        # Tendencia
        ventas = Pago.objects.filter(**filters_pago).annotate(dia=TruncDate('fecha_pago')).values('dia').annotate(total=Sum('monto')).order_by('dia')
        datos_ventas = [{'fecha': v['dia'].strftime('%Y-%m-%d'), 'total': float(v['total'])} for v in ventas]
        promedio = sum(d['total'] for d in datos_ventas) / len(datos_ventas) if datos_ventas else 0

        # Top Servicios
        serv_qs = TicketItem.objects.filter(ticket__fecha_recepcion__date__gte=fecha_inicio, ticket__empresa=empresa)
        if sede: serv_qs = serv_qs.filter(ticket__sede=sede)
        servicios = serv_qs.values('servicio__nombre').annotate(total=Sum(F('cantidad')*F('precio_unitario'))).order_by('-total')[:5]
        datos_servicios = [{'name': s['servicio__nombre'], 'value': float(s['total'] or 0)} for s in servicios]

        # Heatmap
        filters_tkt = {'empresa': empresa, 'fecha_recepcion__date__gte': fecha_inicio}
        if sede: filters_tkt['sede'] = sede
        tickets_h = Ticket.objects.filter(**filters_tkt).annotate(d=ExtractWeekDay('fecha_recepcion'), h=ExtractHour('fecha_recepcion')).values('d', 'h').annotate(c=Count('id'))
        
        dias_lbl = ['DOM', 'LUN', 'MAR', 'MIE', 'JUE', 'VIE', 'SAB']
        heatmap = [{'dia': d, 'manana': 0, 'tarde': 0, 'noche': 0} for d in dias_lbl]
        for item in tickets_h:
            idx = item['d'] - 1 
            if 0 <= idx <= 6:
                h, c = item['h'], item['c']
                if 6 <= h < 12: heatmap[idx]['manana'] += c
                elif 12 <= h < 18: heatmap[idx]['tarde'] += c
                elif 18 <= h <= 23: heatmap[idx]['noche'] += c

        return {
            'ventas_tendencia': datos_ventas,
            'promedio_ventas': promedio,
            'top_servicios': datos_servicios,
            'horas_pico': heatmap
        }

    @staticmethod
    def get_operativo(empresa, sede=None):
        filters = {'activo': True, 'empresa': empresa}
        if sede:
            filters['sede'] = sede

        conteo = Ticket.objects.filter(**filters).aggregate(
            recibidos=Count('id', filter=Q(estado='RECIBIDO')),
            en_proceso=Count('id', filter=Q(estado='EN_PROCESO')),
            listos=Count('id', filter=Q(estado='LISTO')),
            entregados_hoy=Count('id', filter=Q(estado='ENTREGADO', fecha_entrega__date=timezone.localdate()))
        )
        return {'pipeline': conteo}

class ReporteService:
    @staticmethod
    def get_tickets_data(empresa, sede, inicio_dt, fin_dt, estado):
        qs = Ticket.objects.filter(empresa=empresa, activo=True)
        if sede: qs = qs.filter(sede=sede)
        if inicio_dt and fin_dt: qs = qs.filter(fecha_recepcion__range=[inicio_dt, fin_dt])
        if estado and estado != 'TODOS': qs = qs.filter(estado=estado)
        qs = qs.select_related('cliente').order_by('-fecha_recepcion')
        
        registros = []
        total_generado = 0
        for t in qs:
            tot = t.calcular_total()
            total_generado += tot
            registros.append({
                'id': t.numero_ticket,
                'fecha_recepcion': t.fecha_recepcion,
                'cliente': {'nombre': t.cliente.nombre_completo if t.cliente else 'Sin Cliente'},
                'estado': t.estado,
                'total': tot
            })
        return {'registros': registros, 'total_generado': total_generado, 'total_tickets': qs.count()}

    @staticmethod
    def get_caja_pagos_data(empresa, sede, inicio_dt, fin_dt, estado, metodo_pago):
        qs = Pago.objects.filter(ticket__empresa=empresa)
        if estado == 'PAGADO': qs = qs.filter(estado='PAGADO')
        elif estado == 'PENDIENTE': qs = qs.filter(estado='PENDIENTE')
        if metodo_pago and metodo_pago != 'TODOS': qs = qs.filter(metodo_pago_config_id=metodo_pago)
        if sede: qs = qs.filter(ticket__sede=sede)
        if inicio_dt and fin_dt: qs = qs.filter(fecha_pago__range=[inicio_dt, fin_dt])
        qs = qs.select_related('ticket', 'ticket__cliente', 'metodo_pago_config').order_by('-fecha_pago')
        
        registros = []
        total_ingresos = 0
        for p in qs:
            total_ingresos += p.monto
            registros.append({
                'id': p.id,
                'fecha': p.fecha_pago,
                'cliente': p.ticket.cliente.nombre_completo if p.ticket.cliente else 'N/A',
                'metodo': getattr(p.metodo_pago_config, 'nombre_mostrar', p.metodo_pago_snapshot) if p.metodo_pago_config else p.metodo_pago_snapshot,
                'monto': p.monto,
                'estado': p.estado
            })
        return {'registros': registros, 'ingresos': total_ingresos}

    @staticmethod
    def get_diario_electronico_data(empresa, sede, inicio_dt, fin_dt):
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
            if m.tipo == 'INGRESO': total_ingresos += m.monto
            else: total_egresos += m.monto
        
        transacciones.sort(key=lambda x: x['fecha'])
        return {
            'transacciones': transacciones,
            'total_ingresos': total_ingresos,
            'total_egresos': total_egresos,
            'saldo_neto': total_ingresos - total_egresos
        }

    @staticmethod
    def get_ventas_data(empresa, sede, inicio_dt, fin_dt, categoria_servicio):
        from tickets.models import TicketItem
        qs = TicketItem.objects.filter(ticket__empresa=empresa, ticket__activo=True)
        if sede: qs = qs.filter(ticket__sede=sede)
        if inicio_dt and fin_dt: qs = qs.filter(ticket__fecha_recepcion__range=[inicio_dt, fin_dt])
        if categoria_servicio and categoria_servicio != 'TODOS': qs = qs.filter(servicio__categoria_id=categoria_servicio)
            
        qs = qs.values('servicio__nombre').annotate(
            cantidad_total=Sum('cantidad'),
            subtotal=Sum(F('cantidad') * F('precio_unitario'))
        ).order_by('-subtotal')
        
        total_ventas = sum(item['subtotal'] for item in qs if item['subtotal'])
        return {'registros': qs, 'total_ventas': total_ventas}

    @staticmethod
    def get_inventario_data(empresa, sede, categoria_producto, alerta_stock):
        qs = Producto.objects.filter(empresa=empresa, activo=True)
        if sede: qs = qs.filter(sede=sede)
        if categoria_producto and categoria_producto != 'TODOS': qs = qs.filter(categoria_id=categoria_producto)
            
        if alerta_stock == 'BAJO':
            qs = qs.filter(stock_actual__lte=F('stock_minimo'), stock_actual__gt=0)
        elif alerta_stock == 'AGOTADO':
            qs = qs.filter(stock_actual__lte=0)
        return {'registros': qs}

    @staticmethod
    def get_clientes_data(empresa, sede, inicio_date, fin_date, nivel_fidelizacion, estado_deuda):
        qs = Cliente.objects.filter(empresa=empresa)
        if inicio_date and fin_date: qs = qs.filter(fecha_registro__range=[inicio_date, fin_date])
        if sede: qs = qs.filter(sede=sede)
        
        if nivel_fidelizacion == 'NUEVO':
            thirty_days_ago = timezone.now() - timedelta(days=30)
            qs = qs.filter(creado_en__gte=thirty_days_ago)
        elif nivel_fidelizacion == 'VIP':
            qs = qs.annotate(total_gastado_qs=Sum('tickets__pagos__monto', filter=Q(tickets__pagos__estado='PAGADO'))).filter(total_gastado_qs__gte=200)
            
        clientes_finales = []
        for c in qs:
            if estado_deuda == 'DEUDORES':
                saldos = Ticket.objects.filter(cliente=c, empresa=empresa, estado__in=['RECIBIDO', 'EN_PROCESO', 'LISTO']).exclude(estado='ANULADO').exclude(activo=False)
                debt = sum(t.calcular_saldo_pendiente() for t in saldos)
                if debt > 0:
                    c.saldo_pendiente_total = debt
                    clientes_finales.append(c)
            else:
                c.saldo_pendiente_total = 0
                clientes_finales.append(c)
        
        return {'registros': clientes_finales}


