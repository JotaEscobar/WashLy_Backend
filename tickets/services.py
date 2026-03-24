from django.db.models import Q, Sum, F, DecimalField, OuterRef, Subquery, Max, Count, Prefetch
from django.db.models.functions import Coalesce
from django.utils import timezone
from .models import Cliente, Ticket, TicketItem, EstadoHistorial

class ClienteService:
    @staticmethod
    def get_clientes_with_stats(empresa, is_list=True):
        """Obtiene clientes con anotaciones de CRM para la empresa dada"""
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
        try:
            cliente = Cliente.objects.get(pk=pk, empresa=empresa, activo=False)
            cliente.restore()
            return cliente
        except Cliente.DoesNotExist:
            return None

class TicketService:
    @staticmethod
    def get_filtered_tickets(empresa, sede=None, filters_dict=None):
        """Lógica central de filtrado y anotaciones financieras de tickets"""
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
        return {
            'total': queryset.count(),
            'recibidos': queryset.filter(estado='RECIBIDO').count(),
            'en_proceso': queryset.filter(estado='EN_PROCESO').count(),
            'listos': queryset.filter(estado='LISTO').count(),
            'entregados_hoy': queryset.filter(estado='ENTREGADO', fecha_entrega__date=timezone.now().date()).count(),
            'urgentes': queryset.filter(prioridad='URGENTE').count(),
            'express': queryset.filter(prioridad='EXPRESS').count(),
        }
