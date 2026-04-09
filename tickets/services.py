from django.apps import apps

class ClienteService:
    @staticmethod
    def get_clientes_with_stats(empresa, is_list=True):
        """Obtiene clientes con anotaciones de CRM para la empresa dada"""
        from django.db.models import Q, Sum, Max, Count, DecimalField
        from django.db.models.functions import Coalesce
        from django.db.models import Prefetch
        
        Cliente = apps.get_model('tickets', 'Cliente')
        Ticket = apps.get_model('tickets', 'Ticket')
        
        queryset = Cliente.objects.filter(empresa=empresa, activo=True)
        
        # Anotación base: Última visita
        queryset = queryset.annotate(
            ultima_visita=Max('tickets__fecha_recepcion')
        )
        
        if is_list:
            # Optimizaciones para listado
            queryset = queryset.select_related('empresa').annotate(
                total_tickets=Count('tickets'),
                total_gastado=Coalesce(
                    Sum('tickets__pagos__monto', filter=Q(tickets__pagos__estado='PAGADO')),
                    0,
                    output_field=DecimalField()
                )
            )
        else:
            # Optimizaciones para detalle (prefetch)
            queryset = queryset.prefetch_related(
                Prefetch('tickets', queryset=Ticket.objects.filter(activo=True).select_related('sede')),
                'tickets__items',
                'tickets__pagos'
            )
            
        return queryset

    @staticmethod
    def soft_delete(cliente):
        cliente.soft_delete()
        return True

    @staticmethod
    def restore(pk, empresa):
        Cliente = apps.get_model('tickets', 'Cliente')
        try:
            cliente = Cliente.objects.get(pk=pk, empresa=empresa, activo=False)
            cliente.restore()
            return cliente
        except Cliente.DoesNotExist:
            return None

class TicketService:
    @staticmethod
    def set_item_price(item):
        """
        Determina el precio unitario de un item basado en el servicio y prenda.
        Sigue la jerarquía: Precio específico por prenda > Precio base del servicio.
        """
        if not item.precio_unitario and item.servicio:
            if item.prenda:
                # Buscar precio específico de servicio-prenda
                precio_especifico = item.servicio.precios_prendas.filter(
                    prenda=item.prenda
                ).first()
                if precio_especifico:
                    item.precio_unitario = precio_especifico.precio
                else:
                    item.precio_unitario = item.servicio.precio_base
            else:
                item.precio_unitario = item.servicio.precio_base
        return item

    @staticmethod
    def get_filtered_tickets(empresa, sede=None, filters_dict=None):
        """Lógica central de filtrado y anotaciones financieras de tickets"""
        from django.db.models import Q, Sum, F, DecimalField, OuterRef, Subquery
        from django.db.models.functions import Coalesce
        
        Ticket = apps.get_model('tickets', 'Ticket')
        from pagos.models import Pago # Evitar circular import
        
        queryset = Ticket.objects.filter(empresa=empresa, activo=True).select_related(
            'cliente', 'sede'
        ).prefetch_related('items', 'historial_estados')

        if sede:
            queryset = queryset.filter(sede=sede)

        # Subquery: Último método de pago
        ult_pago = Pago.objects.filter(
            ticket=OuterRef('pk'),
            empresa=empresa, 
            estado='PAGADO'
        ).order_by('-fecha_pago')

        queryset = queryset.annotate(
            total_pagado_db=Coalesce(
                Sum('pagos__monto', filter=Q(pagos__estado='PAGADO', pagos__empresa=empresa)), 
                0, 
                output_field=DecimalField()
            ),
            total_ticket_db=Coalesce(
                Sum(F('items__cantidad') * F('items__precio_unitario')),
                0,
                output_field=DecimalField()
            ),
            ultimo_metodo_pago=Subquery(ult_pago.values('metodo_pago_snapshot')[:1])
        ).distinct()

        # Aplicar filtros dinámicos
        if filters_dict:
            if filters_dict.get('estado'):
                queryset = queryset.filter(estado=filters_dict['estado'])
            if filters_dict.get('prioridad'):
                queryset = queryset.filter(prioridad=filters_dict['prioridad'])
            if filters_dict.get('cliente_id'):
                queryset = queryset.filter(cliente_id=filters_dict['cliente_id'])
            if filters_dict.get('fecha_desde'):
                queryset = queryset.filter(fecha_recepcion__date__gte=filters_dict['fecha_desde'])
            if filters_dict.get('fecha_hasta'):
                queryset = queryset.filter(fecha_recepcion__date__lte=filters_dict['fecha_hasta'])
            if filters_dict.get('pendientes_pago') == 'true':
                queryset = queryset.exclude(estado='CANCELADO').filter(
                    total_ticket_db__gt=F('total_pagado_db')
                )

        return queryset

    @staticmethod
    def update_estado(ticket, nuevo_estado, user, comentario=''):
        """Gestiona el cambio de estado, validaciones y creación de historial"""
        estado_anterior = ticket.estado
        
        if nuevo_estado == 'ENTREGADO':
            puede, mensaje = ticket.puede_entregar()
            if not puede:
                return False, mensaje
            ticket.marcar_como_entregado()
        else:
            ticket.estado = nuevo_estado
            ticket.save()

        # Crear historial
        EstadoHistorial = apps.get_model('tickets', 'EstadoHistorial')
        EstadoHistorial.objects.create(
            ticket=ticket,
            empresa=ticket.empresa,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado,
            creado_por=user,
            comentario=comentario
        )
        return True, "Estado actualizado"

    @staticmethod
    def cancel_ticket(ticket, user, motivo=''):
        """Cancela un ticket si es posible"""
        if ticket.estado == 'ENTREGADO':
            return False, "No se puede cancelar un ticket ya entregado"
        
        estado_anterior = ticket.estado
        ticket.estado = 'CANCELADO'
        ticket.save()
        
        EstadoHistorial = apps.get_model('tickets', 'EstadoHistorial')
        EstadoHistorial.objects.create(
            ticket=ticket,
            empresa=ticket.empresa,
            estado_anterior=estado_anterior,
            estado_nuevo='CANCELADO',
            creado_por=user,
            comentario=motivo or "Ticket cancelado"
        )
        return True, "Ticket cancelado"

    @staticmethod
    def get_dashboard_stats(queryset):
        """Calcula estadísticas rápidas para el dashboard"""
        from django.utils import timezone
        return {
            'total': queryset.count(),
            'recibidos': queryset.filter(estado='RECIBIDO').count(),
            'en_proceso': queryset.filter(estado='EN_PROCESO').count(),
            'listos': queryset.filter(estado='LISTO').count(),
            'entregados_hoy': queryset.filter(estado='ENTREGADO', fecha_entrega__date=timezone.now().date()).count(),
            'urgentes': queryset.filter(prioridad='URGENTE').count(),
            'express': queryset.filter(prioridad='EXPRESS').count(),
        }

    @staticmethod
    def prepare_new_ticket(ticket):
        """
        Lógica de inicialización para nuevos tickets:
        - Generación de secuencial único por empresa
        - Generación de número de ticket formateado
        - Generación de código QR
        """
        from core.utils import generar_numero_unico, generar_qr_code
        from django.db import transaction

        # 1. Generar número y secuencial si no existe
        if not ticket.numero_ticket and ticket.empresa:
            with transaction.atomic():
                try:
                    prefijo = ticket.empresa.ticket_prefijo or 'TK-'
                except AttributeError:
                    prefijo = 'TK-'
                
                Ticket = apps.get_model('tickets', 'Ticket')
                ultimo = Ticket.objects.select_for_update().filter(
                    empresa=ticket.empresa
                ).order_by('-secuencial').first()
                
                nuevo_sec = (ultimo.secuencial + 1) if ultimo else 1
                ticket.secuencial = nuevo_sec
                ticket.numero_ticket = f"{prefijo}{str(nuevo_sec).zfill(6)}"
        
        # Fallback de número único
        if not ticket.numero_ticket:
             ticket.numero_ticket = generar_numero_unico(prefijo='TKT')

        return ticket
