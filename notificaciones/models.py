"""
Modelos para gestión de notificaciones
"""

from django.db import models
from core.models import AuditModel
from tickets.models import Cliente, Ticket


class Notificacion(AuditModel):
    CANAL_CHOICES = [
        ('EMAIL', 'Email'),
        ('WHATSAPP', 'WhatsApp'),
        ('SMS', 'SMS'),
    ]
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ENVIADO', 'Enviado'),
        ('ERROR', 'Error'),
    ]
    
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='notificaciones', null=True, blank=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='notificaciones', null=True, blank=True)
    
    destinatario = models.CharField(max_length=200)
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES)
    asunto = models.CharField(max_length=500, blank=True)
    mensaje = models.TextField()
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    fecha_envio = models.DateTimeField(null=True, blank=True)
    error_mensaje = models.TextField(blank=True)
    intentos = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ['-creado_en']
    
    def __str__(self):
        return f"{self.canal} - {self.destinatario} - {self.estado}"
