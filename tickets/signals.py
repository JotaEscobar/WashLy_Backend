"""
Signals para la app tickets
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Ticket, EstadoHistorial


@receiver(pre_save, sender=Ticket)
def ticket_estado_cambiado(sender, instance, **kwargs):
    """
    Signal que se ejecuta antes de guardar un ticket
    Detecta cambios de estado para crear historial
    """
    if instance.pk:  # Solo si el ticket ya existe
        try:
            ticket_anterior = Ticket.objects.get(pk=instance.pk)
            if ticket_anterior.estado != instance.estado:
                # El estado ha cambiado
                pass
        except Ticket.DoesNotExist:
            pass


@receiver(post_save, sender=EstadoHistorial)
def enviar_notificacion_cambio_estado(sender, instance, created, **kwargs):
    """
    Signal que envía notificación cuando cambia el estado de un ticket
    """
    if created:
        # NOTA: Deshabilitado temporalmente para desarrollo local sin Redis/Celery
        # from notificaciones.tasks import enviar_notificacion_ticket
        
        # Mensajes según el estado
        mensajes = {
            'RECIBIDO': 'Su orden ha sido recibida y está en proceso de registro.',
            'EN_PROCESO': 'Su ropa está siendo procesada. Le avisaremos cuando esté lista.',
            'LISTO': '¡Su ropa está lista! Puede pasar a recogerla en nuestro local.',
            'ENTREGADO': 'Gracias por confiar en Washly. ¡Esperamos verle pronto!',
            'CANCELADO': 'Su orden ha sido cancelada. Si tiene dudas, contáctenos.'
        }
        
        mensaje = mensajes.get(
            instance.estado_nuevo,
            f'Su ticket {instance.ticket.numero_ticket} cambió a {instance.estado_nuevo}'
        )
        
        # Enviar notificación (tarea asíncrona) - DESHABILITADO
        # try:
        #     enviar_notificacion_ticket.delay(
        #         ticket_id=instance.ticket.id,
        #         mensaje=mensaje,
        #         canales=['EMAIL', 'WHATSAPP']
        #     )
        # except Exception as e:
        #     # Log del error pero no bloquear el flujo
        #     print(f"Error al enviar notificación: {e}")
        pass