"""
Signals para la app tickets
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Ticket, EstadoHistorial



@receiver(post_save, sender=EstadoHistorial)
def enviar_notificacion_cambio_estado(sender, instance, created, **kwargs):
    """
    Signal que envía notificación cuando cambia el estado de un ticket.
    NOTA: Se implementará la lógica real conectada a Gmail en la Fase 8.
    """
    pass