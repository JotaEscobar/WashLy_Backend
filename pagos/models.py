from django.db import models
from django.conf import settings
from core.models import AuditModel
from tickets.models import Ticket
from core.utils import generar_numero_unico

class CajaSesion(AuditModel):
    """
    Representa un turno o día de caja. 
    Todo pago o movimiento debe pertenecer temporalmente a una sesión abierta.
    """
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    
    monto_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Datos de Cierre
    monto_sistema = models.DecimalField(max_digits=10, decimal_places=2, default=0) # Calculado
    monto_real = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # Contado por humano
    diferencia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    estado = models.CharField(max_length=10, default='ABIERTA', choices=[('ABIERTA', 'Abierta'), ('CERRADA', 'Cerrada')])
    comentarios = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Caja {self.id} - {self.usuario.username} ({self.estado})"

class Pago(AuditModel):
    """
    Ingreso de dinero vinculado estrictamente a un Ticket (Venta)
    """
    METODOS = [
        ('EFECTIVO', 'Efectivo'), ('TARJETA', 'Tarjeta'),
        ('YAPE', 'Yape'), ('PLIN', 'Plin'), ('TRANSFERENCIA', 'Transferencia')
    ]
    
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='pagos')
    caja = models.ForeignKey(CajaSesion, on_delete=models.PROTECT, related_name='pagos_ticket', null=True, blank=True) # Se vincula a la caja activa
    
    numero_pago = models.CharField(max_length=50, unique=True, editable=False)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODOS)
    
    estado = models.CharField(max_length=20, default='PAGADO', choices=[('PAGADO', 'Pagado'), ('ANULADO', 'Anulado')])
    referencia = models.CharField(max_length=100, blank=True, null=True) # Nro Operación
    fecha_pago = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.numero_pago:
            self.numero_pago = generar_numero_unico('PAG')
        # Al guardar, intentamos asignar la caja abierta del usuario si no tiene
        if not self.caja and self.creado_por:
            caja_abierta = CajaSesion.objects.filter(usuario=self.creado_por, estado='ABIERTA').first()
            if caja_abierta:
                self.caja = caja_abierta
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero_pago} - {self.monto}"

class MovimientoCaja(AuditModel):
    """
    Ingresos o Egresos manuales (Gastos, Retiros, Aportes)
    """
    caja = models.ForeignKey(CajaSesion, on_delete=models.CASCADE, related_name='movimientos_extra')
    tipo = models.CharField(max_length=10, choices=[('INGRESO', 'Ingreso'), ('EGRESO', 'Egreso/Gasto')])
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.CharField(max_length=255)
    categoria = models.CharField(max_length=50, default='GENERAL') # Proveedores, Servicios, Personal...

    def __str__(self):
        return f"{self.tipo} - {self.monto}"