from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, time, timedelta
import json
from .models import Pago, CajaSesion, MovimientoCaja, MetodoPagoConfig

from django.db import transaction

def registrar_pago(user, empresa, ticket, monto, metodo_pago_id=None, metodo_pago_str=None, referencia=None):
    """
    Servicio centralizado para registrar pagos, asegurando que se validen contra la caja
    abierta del usuario y se asigne el método de pago correcto.
    Usa bloqueos pesimistas para asegurar IDEMPOTENCIA contra múltiples clics.
    """
    monto_float = float(monto)
    if monto_float <= 0:
        return None
    # Envolver la operación en una transacción atómica para evitar "Race Conditions"
    with transaction.atomic():
        # 1. Bloqueo Pesimista: Obtenemos el ticket y bloqueamos la fila hasta terminar
        from tickets.models import Ticket
        locked_ticket = Ticket.objects.select_for_update().get(id=ticket.id)
        
        # 2. Idempotencia: Verificar que el ticket no se "sobre-pague" por clics dobles
        saldo_actual = locked_ticket.calcular_saldo_pendiente()
        if round(monto_float, 2) > round(float(saldo_actual), 2):
            raise serializers.ValidationError({
                "error": f"IDEMPOTENCIA ALERT: Intento de pago por S/{monto_float} supera el saldo pendiente de S/{saldo_actual}. Transacción rechazada para evitar sobre-cobro."
            })

        # Validar Caja Abierta (Dentro del lock para consistencia total si se requiere)
        caja_abierta = CajaSesion.objects.filter(
            usuario=user, 
            empresa=empresa, 
            estado='ABIERTA'
        ).first()
        
        if not caja_abierta:
            raise serializers.ValidationError({
                "error": "No tienes una caja abierta. Apertura caja para recibir pagos."
            })
        
        # Resolver Configuración del Método de Pago
        metodo_config = None
        if metodo_pago_id:
            metodo_config = MetodoPagoConfig.objects.filter(id=metodo_pago_id, empresa=empresa).first()
        elif metodo_pago_str:
            metodo_config = MetodoPagoConfig.objects.filter(
                codigo_metodo=metodo_pago_str.upper(), 
                empresa=empresa
            ).first()

        snapshot = metodo_config.nombre_mostrar if metodo_config else (metodo_pago_str or "EFECTIVO")
        if not referencia:
            referencia = f'Pago Ticket {ticket.numero_ticket}'

        # Registrar el Pago DENTRO de la transacción y lock
        pago = Pago.objects.create(
            ticket=locked_ticket,  # Usar el objeto bloqueado
            caja=caja_abierta,
            monto=monto,
            metodo_pago_config=metodo_config,
            metodo_pago_snapshot=snapshot,
            estado='PAGADO',
            referencia=referencia,
            empresa=empresa,
            creado_por=user
        )
        
        return pago

class CajaService:
    @staticmethod
    def _format_pago_event(p):
        """Helper para formatear un evento de pago consistentemente"""
        desc = f"Pago Ticket #{p.ticket.numero_ticket}"
        if p.estado == 'ANULADO':
            desc += " (ANULADO)"
        
        cliente_nombre = "N/A"
        if hasattr(p.ticket, 'cliente') and p.ticket.cliente:
            cliente_nombre = p.ticket.cliente.nombre_completo
        
        metodo_nombre = p.metodo_pago_snapshot or (p.metodo_pago_config.nombre_mostrar if p.metodo_pago_config else "N/A")

        return {
            'id': f'pago-{p.id}',
            'hora_raw': p.fecha_pago,
            'tipo_evento': 'VENTA',
            'fecha': p.fecha_pago,
            'monto': p.monto,
            'descripcion': desc,
            'usuario': p.creado_por.username if p.creado_por else 'Sistema',
            'es_entrada': True,
            'estado': p.estado,
            'detalles': {
                'MÉTODO': metodo_nombre, 
                'TICKET': p.ticket.numero_ticket, 
                'CLIENTE': cliente_nombre
            }
        }

    @staticmethod
    def _format_movimiento_event(m):
        """Helper para formatear un evento de movimiento de caja consistentemente"""
        tipo_texto = "Gasto" if m.tipo == 'EGRESO' else "Ingreso"
        desc = f"{tipo_texto} - {m.categoria}: {m.descripcion}"
        metodo_nombre = m.metodo_pago_config.nombre_mostrar if m.metodo_pago_config else "EFECTIVO"
        
        return {
            'id': f'mov-{m.id}',
            'hora_raw': m.creado_en,
            'tipo_evento': m.tipo,
            'fecha': m.creado_en,
            'monto': m.monto,
            'descripcion': desc,
            'usuario': m.creado_por.username if m.creado_por else 'Sistema',
            'es_entrada': m.tipo == 'INGRESO',
            'estado': 'OK',
            'detalles': {
                'TIPO': tipo_texto.upper(), 
                'CATEGORÍA': m.categoria, 
                'MÉTODO': metodo_nombre, 
                'NOTA': m.descripcion
            }
        }

    @staticmethod
    def _ensure_dict(data):
        """Asegura que los datos de un JSONField sean un diccionario, manejando strings y None."""
        if not data:
            return {}
        if isinstance(data, str):
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return {}
        return data if isinstance(data, dict) else {}
        
    @staticmethod
    def _clean_comment(comment):
        """Elimina la cadena técnica '| Detalle Cierre: [...]' de los comentarios antiguos."""
        if not comment:
            return ""
        if ' | Detalle Cierre:' in comment:
            return comment.split(' | Detalle Cierre:')[0].strip()
        return comment.strip()

    @staticmethod
    def build_timeline_events(caja):
        events = []
        
        # 1. Apertura
        apertura_detalle = CajaService._ensure_dict(caja.detalle_apertura)
        if 'EFECTIVO' not in apertura_detalle:
            apertura_detalle['EFECTIVO'] = float(caja.monto_inicial)
        
        # Solo mostrar COMENTARIOS en apertura si existen dentro del detalle específico de apertura
        # (Actualmente el frontend no los envía, por lo que aparecerá limpio/vacío como debe ser)
        if 'comentarios' in apertura_detalle:
            apertura_detalle['COMENTARIOS'] = apertura_detalle['comentarios']
            
        events.append({
            'id': f'apertura-{caja.id}',
            'hora_raw': caja.fecha_apertura,
            'tipo_evento': 'APERTURA',
            'fecha': caja.fecha_apertura,
            'monto': caja.monto_inicial,
            'descripcion': f'Apertura de Caja (ID: {caja.id})',
            'usuario': caja.usuario.username,
            'es_entrada': True,
            'estado': 'OK',
            'detalles': apertura_detalle
        })
        
        # 2. Pagos
        pagos = Pago.objects.filter(caja=caja).select_related('ticket', 'ticket__cliente', 'metodo_pago_config')
        for p in pagos:
            events.append(CajaService._format_pago_event(p))
            
        # 3. Movimientos
        movimientos = caja.movimientos_extra.all().select_related('metodo_pago_config')
        for m in movimientos:
            events.append(CajaService._format_movimiento_event(m))
            
        # 4. Cierre
        if caja.fecha_cierre and caja.estado == 'CERRADA':
            cierre_detalle = CajaService._ensure_dict(caja.detalle_cierre)
            cierre_detalle_filtrado = {k: v for k, v in cierre_detalle.items() if k not in ['TRANSFERENCIA', 'comentarios']}
            
            # Para el cierre, priorizar el campo comentarios de la sesión (donde se guarda el cierre)
            if caja.comentarios:
                cierre_detalle_filtrado['COMENTARIOS'] = CajaService._clean_comment(caja.comentarios)
            elif 'comentarios' in cierre_detalle:
                 cierre_detalle_filtrado['COMENTARIOS'] = CajaService._clean_comment(cierre_detalle['comentarios'])
            
            events.append({
                'id': f'cierre-{caja.id}',
                'hora_raw': caja.fecha_cierre,
                'tipo_evento': 'CIERRE',
                'fecha': caja.fecha_cierre,
                'monto': caja.monto_final_real or 0,
                'descripcion': f'Cierre de Caja (Dif: {caja.diferencia})',
                'usuario': caja.usuario.username,
                'es_entrada': None, 
                'estado': 'OK',
                'detalles': cierre_detalle_filtrado
            })
        return events

    @staticmethod
    def get_diario_events(empresa, sede, start_aware, end_aware):
        events = []
        
        # 1. Pagos
        pagos = Pago.objects.filter(
            empresa=empresa,
            fecha_pago__gte=start_aware,
            fecha_pago__lte=end_aware
        ).select_related('ticket', 'creado_por', 'ticket__cliente', 'metodo_pago_config')
        
        if sede:
            pagos = pagos.filter(ticket__sede=sede)
        
        for p in pagos:
            desc = f"Pago Ticket #{p.ticket.numero_ticket}"
            if p.estado == 'ANULADO': desc += " (ANULADO)"
            
            cliente_nombre = p.ticket.cliente.nombre_completo if p.ticket.cliente else "N/A"
            metodo_nombre = p.metodo_pago_snapshot or (p.metodo_pago_config.nombre_mostrar if p.metodo_pago_config else "N/A")
            
            events.append({
                'id': f'pago-{p.id}',
                'hora_raw': p.fecha_pago,
                'tipo_evento': 'VENTA',
                'fecha': p.fecha_pago,
                'monto': p.monto,
                'descripcion': desc,
                'usuario': p.creado_por.username if p.creado_por else 'Sistema',
                'es_entrada': True,
                'estado': p.estado,
                'detalles': {
                    'MÉTODO': metodo_nombre,
                    'TICKET': p.ticket.numero_ticket,
                    'CLIENTE': cliente_nombre
                }
            })

        # 2. Movimientos
        movimientos = MovimientoCaja.objects.filter(
            empresa=empresa,
            creado_en__gte=start_aware,
            creado_en__lte=end_aware
        ).select_related('creado_por', 'metodo_pago_config')
        
        if sede:
            movimientos = movimientos.filter(caja__sede=sede)
        
        for m in movimientos:
            tipo_texto = "Gasto" if m.tipo == 'EGRESO' else "Ingreso"
            desc = f"{tipo_texto} - {m.categoria}: {m.descripcion}"
            metodo_nombre = m.metodo_pago_config.nombre_mostrar if m.metodo_pago_config else "EFECTIVO"
            
            events.append({
                'id': f'mov-{m.id}',
                'hora_raw': m.creado_en,
                'tipo_evento': m.tipo,
                'fecha': m.creado_en,
                'monto': m.monto,
                'descripcion': desc,
                'usuario': m.creado_por.username if m.creado_por else 'Sistema',
                'es_entrada': m.tipo == 'INGRESO',
                'estado': 'OK',
                'detalles': {
                    'TIPO': tipo_texto.upper(),
                    'CATEGORÍA': m.categoria,
                    'MÉTODO': metodo_nombre,
                    'NOTA': m.descripcion
                }
            })

        # 3. Aperturas
        aperturas = CajaSesion.objects.filter(
            empresa=empresa,
            fecha_apertura__gte=start_aware,
            fecha_apertura__lte=end_aware
        ).select_related('usuario')
        
        if sede:
            aperturas = aperturas.filter(sede=sede)

        for c in aperturas:
            detalle = CajaService._ensure_dict(c.detalle_apertura)
            if 'EFECTIVO' not in detalle:
                detalle['EFECTIVO'] = float(c.monto_inicial)
            
            # Solo mostrar comentarios en apertura si están en su detalle
            if 'comentarios' in detalle:
                detalle['COMENTARIOS'] = detalle['comentarios']
                
            events.append({
                'id': f'apertura-{c.id}',
                'hora_raw': c.fecha_apertura,
                'tipo_evento': 'APERTURA',
                'fecha': c.fecha_apertura,
                'monto': c.monto_inicial,
                'descripcion': f'Apertura de Caja',
                'usuario': c.usuario.username,
                'es_entrada': True,
                'estado': 'OK',
                'detalles': detalle
            })

        # 4. Cierres
        cierres = CajaSesion.objects.filter(
            empresa=empresa,
            fecha_cierre__gte=start_aware,
            fecha_cierre__lte=end_aware,
            estado='CERRADA'
        ).select_related('usuario')
        
        if sede:
            cierres = cierres.filter(sede=sede)

        for c in cierres:
            detalle = CajaService._ensure_dict(c.detalle_cierre)
            detalle_filtrado = {k: v for k, v in detalle.items() if k not in ['TRANSFERENCIA', 'comentarios']}
            
            # Priorizar el campo comentarios de la sesión para el cierre
            if c.comentarios:
                detalle_filtrado['COMENTARIOS'] = CajaService._clean_comment(c.comentarios)
            elif 'comentarios' in detalle:
                detalle_filtrado['COMENTARIOS'] = CajaService._clean_comment(detalle['comentarios'])
            
            events.append({
                'id': f'cierre-{c.id}',
                'hora_raw': c.fecha_cierre,
                'tipo_evento': 'CIERRE',
                'fecha': c.fecha_cierre,
                'monto': c.monto_final_real or 0,
                'descripcion': f'Cierre de Caja',
                'usuario': c.usuario.username,
                'es_entrada': None,
                'estado': 'OK',
                'detalles': detalle_filtrado
            })

        return events
