from django.db import models
from django.conf import settings
from core.models import AuditModel, Empresa, Sede, TimeStampedModel
from tickets.models import Ticket
from core.utils import generar_numero_unico

class MetodoPagoConfig(TimeStampedModel):
    """
    Configuración de métodos de pago por Empresa
    """
    METODOS_BASE = [
        ('EFECTIVO', 'Efectivo'),
        ('TARJETA', 'Tarjeta de Crédito/Débito'),
        ('YAPE', 'Yape'),
        ('PLIN', 'Plin'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='metodos_pago')
    codigo_metodo = models.CharField(max_length=20, choices=METODOS_BASE)
    nombre_mostrar = models.CharField(max_length=50, verbose_name="Nombre a mostrar (Ej: Yape de Juan)")
    
    activo = models.BooleanField(default=True)
    
    # Datos para pagos digitales
    numero_cuenta = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número / Teléfono")
    imagen_qr = models.ImageField(upload_to='pagos/qrs/', null=True, blank=True)
    instrucciones = models.TextField(blank=True)

    class Meta:
        unique_together = ['empresa', 'codigo_metodo', 'numero_cuenta']

    def __str__(self):
        return f"{self.nombre_mostrar} ({self.empresa.nombre})"


class CajaSesion(AuditModel):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, null=True, blank=True, related_name='cajas_sesion')
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    
    monto_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monto_final_sistema = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monto_final_real = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    diferencia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    detalle_apertura = models.JSONField(default=dict, verbose_name="Detalle de Apertura") 
    detalle_cierre = models.JSONField(default=dict, verbose_name="Detalle de Cierre")
    estado = models.CharField(max_length=10, default='ABIERTA', choices=[('ABIERTA', 'Abierta'), ('CERRADA', 'Cerrada')])
    comentarios = models.TextField(blank=True, null=True)

    def __str__(self):
        sede_str = self.sede.nombre if self.sede else 'Sede (Global)'
        return f"Caja {self.id} - {self.usuario.username} ({sede_str})"


class Pago(AuditModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='pagos')
    caja = models.ForeignKey(CajaSesion, on_delete=models.PROTECT, related_name='pagos_ticket', null=True, blank=True)
    
    # Vinculamos al método configurado
    metodo_pago_config = models.ForeignKey(MetodoPagoConfig, on_delete=models.PROTECT, null=True)
    metodo_pago_snapshot = models.CharField(max_length=50) 
    
    numero_pago = models.CharField(max_length=50, editable=False)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, default='PAGADO', choices=[('PAGADO', 'Pagado'), ('ANULADO', 'Anulado')])
    referencia = models.CharField(max_length=100, blank=True, null=True)
    fecha_pago = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.numero_pago:
            self.numero_pago = generar_numero_unico('PAG')
        
        if self.metodo_pago_config:
            self.metodo_pago_snapshot = self.metodo_pago_config.nombre_mostrar
            
        if not self.caja and self.creado_por:
            # Buscar caja abierta que coincida con la sede del ticket
            caja_filters = {
                'empresa': self.empresa, 
                'usuario': self.creado_por, 
                'estado': 'ABIERTA'
            }
            if self.ticket and self.ticket.sede:
                caja_filters['sede'] = self.ticket.sede
            caja_abierta = CajaSesion.objects.filter(**caja_filters).first()
            if caja_abierta:
                self.caja = caja_abierta
        super().save(*args, **kwargs)


class MovimientoCaja(AuditModel):
    caja = models.ForeignKey(CajaSesion, on_delete=models.CASCADE, related_name='movimientos_extra')
    tipo = models.CharField(max_length=10, choices=[('INGRESO', 'Ingreso'), ('EGRESO', 'Egreso/Gasto')])
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    
    metodo_pago_config = models.ForeignKey(MetodoPagoConfig, on_delete=models.SET_NULL, null=True, blank=True)
    
    descripcion = models.CharField(max_length=255)
    categoria = models.CharField(max_length=50, default='GENERAL')