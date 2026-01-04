"""
Tareas asíncronas para notificaciones
"""

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


@shared_task
def enviar_notificacion_ticket(ticket_id, mensaje, canales=None):
    """
    Envía notificación sobre un ticket
    """
    from tickets.models import Ticket
    from .models import Notificacion
    
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        cliente = ticket.cliente
        
        if canales is None:
            canales = ['EMAIL']
        
        for canal in canales:
            if canal == 'EMAIL' and cliente.email:
                enviar_email.delay(
                    ticket_id=ticket.id,
                    destinatario=cliente.email,
                    asunto=f"Washly - Ticket {ticket.numero_ticket}",
                    mensaje=mensaje
                )
            
            elif canal == 'WHATSAPP' and cliente.telefono:
                enviar_whatsapp.delay(
                    ticket_id=ticket.id,
                    destinatario=cliente.telefono,
                    mensaje=mensaje
                )
    
    except Exception as e:
        print(f"Error en enviar_notificacion_ticket: {e}")


@shared_task
def enviar_email(ticket_id, destinatario, asunto, mensaje):
    """
    Envía notificación por email
    """
    from tickets.models import Ticket
    from .models import Notificacion
    
    try:
        ticket = Ticket.objects.get(id=ticket_id) if ticket_id else None
        
        # Crear registro de notificación
        notif = Notificacion.objects.create(
            ticket=ticket,
            cliente=ticket.cliente if ticket else None,
            destinatario=destinatario,
            canal='EMAIL',
            asunto=asunto,
            mensaje=mensaje,
            estado='PENDIENTE'
        )
        
        # Enviar email
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinatario],
            fail_silently=False,
        )
        
        # Actualizar estado
        notif.estado = 'ENVIADO'
        notif.fecha_envio = timezone.now()
        notif.save()
        
        return True
    
    except Exception as e:
        if 'notif' in locals():
            notif.estado = 'ERROR'
            notif.error_mensaje = str(e)
            notif.intentos += 1
            notif.save()
        return False


@shared_task
def enviar_whatsapp(ticket_id, destinatario, mensaje):
    """
    Envía notificación por WhatsApp usando Twilio
    """
    from tickets.models import Ticket
    from .models import Notificacion
    
    try:
        ticket = Ticket.objects.get(id=ticket_id) if ticket_id else None
        
        # Crear registro de notificación
        notif = Notificacion.objects.create(
            ticket=ticket,
            cliente=ticket.cliente if ticket else None,
            destinatario=destinatario,
            canal='WHATSAPP',
            mensaje=mensaje,
            estado='PENDIENTE'
        )
        
        # Aquí iría la integración real con Twilio
        # from twilio.rest import Client
        # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        # message = client.messages.create(
        #     from_=f"whatsapp:{settings.TWILIO_WHATSAPP_FROM}",
        #     to=f"whatsapp:{destinatario}",
        #     body=mensaje
        # )
        
        # Por ahora, solo simulamos el envío
        print(f"[WHATSAPP SIMULADO] A: {destinatario} - Mensaje: {mensaje}")
        
        # Actualizar estado
        notif.estado = 'ENVIADO'
        notif.fecha_envio = timezone.now()
        notif.save()
        
        return True
    
    except Exception as e:
        if 'notif' in locals():
            notif.estado = 'ERROR'
            notif.error_mensaje = str(e)
            notif.intentos += 1
            notif.save()
        return False


@shared_task
def verificar_alertas_stock():
    """
    Verifica productos con stock bajo y envía alertas
    """
    from inventario.models import Producto, AlertaStock
    
    productos_bajo_stock = Producto.objects.filter(
        activo=True,
        stock_actual__lte=models.F('stock_minimo')
    )
    
    for producto in productos_bajo_stock:
        # Verificar si ya hay una alerta activa
        alerta_activa = AlertaStock.objects.filter(
            producto=producto,
            resuelta=False
        ).exists()
        
        if not alerta_activa:
            nivel = 'CRITICO' if producto.stock_critico else 'BAJO'
            AlertaStock.objects.create(
                producto=producto,
                nivel=nivel,
                stock_actual=producto.stock_actual
            )
            
            # Enviar notificación a administradores
            print(f"[ALERTA] Stock {nivel} de {producto.nombre}: {producto.stock_actual} {producto.unidad_medida}")
