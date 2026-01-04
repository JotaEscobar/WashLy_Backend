"""
Modelos para gestión de pagos
"""

from django.db import models
from core.models import AuditModel
from tickets.models import Ticket


class Pago(AuditModel):
    METODO_PAGO_CHOICES = [
        ('EFECTIVO', 'Efectivo'),
        ('TARJETA', 'Tarjeta de Crédito/Débito'),
        ('YAPE', 'Yape'),
        ('PLIN', 'Plin'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('OTRO', 'Otro'),
    ]
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADO', 'Pagado'),
        ('CANCELADO', 'Cancelado'),
        ('DEVUELTO', 'Devuelto'),
    ]
    
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='pagos')
    numero_pago = models.CharField(max_length=50, unique=True, db_index=True)
    
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    
    fecha_pago = models.DateTimeField(auto_now_add=True)
    referencia = models.CharField(max_length=200, blank=True)
    notas = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ['-fecha_pago']
        indexes = [
            models.Index(fields=['numero_pago']),
            models.Index(fields=['ticket', 'estado']),
        ]
    
    def __str__(self):
        return f"Pago {self.numero_pago} - {self.ticket.numero_ticket} - S/ {self.monto}"
    
    def save(self, *args, **kwargs):
        if not self.numero_pago:
            from core.utils import generar_numero_unico
            self.numero_pago = generar_numero_unico(prefijo='PAG')
        super().save(*args, **kwargs)
