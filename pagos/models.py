from django.db import models
from django.conf import settings
from core.models import AuditModel, Empresa, TimeStampedModel
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
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
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
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    
    monto_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monto_final_sistema = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monto_final_real = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    diferencia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    detalle_apertura = models.TextField(default="{}") 
    detalle_cierre = models.TextField(default="{}")
    estado = models.CharField(max_length=10, default='ABIERTA', choices=[('ABIERTA', 'Abierta'), ('CERRADA', 'Cerrada')])
    comentarios = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Caja {self.id} - {self.usuario.username}"


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
            caja_abierta = CajaSesion.objects.filter(
                empresa=self.empresa, 
                usuario=self.creado_por, 
                estado='ABIERTA'
            ).first()
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