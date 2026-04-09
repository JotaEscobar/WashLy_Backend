"""
Modelos para la gestión de tickets/órdenes de servicio
Actualizado para SaaS (Multi-tenant) con lógica de negocio completa
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from core.models import AuditModel, SoftDeleteModel, Sede, Empresa, TimeStampedModel
from core.utils import generar_numero_unico, generar_qr_code
from django.utils import timezone
from .constants import TicketEstados, TicketPrioridades  # ✅ Importar constantes





class Cliente(AuditModel, SoftDeleteModel):
    """Modelo de Cliente (SaaS)"""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('DNI', 'DNI'),
        ('RUC', 'RUC'),
        ('CE', 'Carnet de Extranjería'),
        ('PASAPORTE', 'Pasaporte'),
    ]
    
    tipo_documento = models.CharField(max_length=20, choices=TIPO_DOCUMENTO_CHOICES, default='DNI')
    numero_documento = models.CharField(max_length=20, verbose_name="Número de documento")
    nombres = models.CharField(max_length=200, verbose_name="Nombres")
    apellidos = models.CharField(max_length=200, verbose_name="Apellidos", blank=True)
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    direccion = models.TextField(blank=True, verbose_name="Dirección")
    
    # Campos para marketing y CRM
    fecha_registro = models.DateField(auto_now_add=True, verbose_name="Fecha de registro")
    notas = models.TextField(blank=True, verbose_name="Notas")
    preferencias = models.JSONField(default=dict, blank=True, verbose_name="Preferencias")
    
    # Relación con sede (Opcional, si el cliente pertenece a una sede específica)
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        related_name='clientes',
        verbose_name="Sede",
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['-creado_en']
        # VALIDACIÓN SAAS: El documento debe ser único POR EMPRESA
        unique_together = ['empresa', 'tipo_documento', 'numero_documento']
        indexes = [
            models.Index(fields=['numero_documento']),
            models.Index(fields=['telefono']),
            models.Index(fields=['email']),  # ✅ Índice para búsquedas
        ]
    
    def __str__(self):
        return f"{self.nombres} {self.apellidos} - {self.numero_documento}"
    
    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".strip()


class Ticket(AuditModel, SoftDeleteModel):
    """Modelo principal de Ticket/Orden de Servicio (SaaS)"""
    
    # ✅ Usar constantes importadas
    ESTADO_CHOICES = TicketEstados.CHOICES
    PRIORIDAD_CHOICES = TicketPrioridades.CHOICES

    TIPO_ENTREGA_CHOICES = [
            ('RECOJO', 'Recojo en Tienda'),
            ('DELIVERY', 'Delivery'),
    ]
    
    # Identificación única
    numero_ticket = models.CharField(
        max_length=50,
        verbose_name="Número de Ticket",
        db_index=True
    )
    
    # Nuevo campo SaaS: Secuencial humano reseteable por empresa
    secuencial = models.PositiveIntegerField(default=0, verbose_name="Secuencial Humano")
    
    # Campo para rastreo público seguro (no adivinable)
    tracking_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='tickets',
        verbose_name="Cliente"
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name="Sede",
        null=True,
        blank=True
    )
    
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=TicketEstados.RECIBIDO,  # ✅ Usar constante
        verbose_name="Estado"
    )
    prioridad = models.CharField(
        max_length=20,
        choices=PRIORIDAD_CHOICES,
        default=TicketPrioridades.NORMAL,  # ✅ Usar constante
        verbose_name="Prioridad"
    )
    tipo_entrega = models.CharField(
        max_length=20, 
        choices=TIPO_ENTREGA_CHOICES, 
        default='RECOJO',
        verbose_name="Tipo de Entrega"
    )
    
    fecha_recepcion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Recepción")
    fecha_prometida = models.DateTimeField(verbose_name="Fecha Prometida de Entrega")
    fecha_entrega = models.DateTimeField(null=True, blank=True, verbose_name="Fecha Real de Entrega")
    
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ['-fecha_recepcion']
        # VALIDACIÓN SAAS: El número de ticket es único POR EMPRESA
        unique_together = ['empresa', 'numero_ticket']
        indexes = [
            models.Index(fields=['numero_ticket']),
            models.Index(fields=['estado', 'fecha_recepcion']),
            models.Index(fields=['cliente', 'fecha_recepcion']),
        ]
    
    def __str__(self):
        return f"Ticket {self.numero_ticket} - {self.cliente.nombre_completo}"
    
    def save(self, *args, **kwargs):
        from .services import TicketService
        # Delegamos la generación de número y QR al servicio (SRP)
        TicketService.prepare_new_ticket(self)
        super().save(*args, **kwargs)
    
    # --- MÉTODOS DE NEGOCIO ORIGINALES RESTAURADOS ---

    def calcular_total(self):
        """Calcula el total del ticket sumando todos los items"""
        return self.items.aggregate(
            total=models.Sum(models.F('cantidad') * models.F('precio_unitario'))
        )['total'] or 0
    
    def calcular_saldo_pendiente(self):
        """Calcula el saldo pendiente de pago"""
        from pagos.models import Pago
        total = self.calcular_total()
        pagado = Pago.objects.filter(
            ticket=self,
            estado='PAGADO'
        ).aggregate(total=models.Sum('monto'))['total'] or 0
        return total - pagado
    
    def esta_pagado(self):
        """Verifica si el ticket está completamente pagado"""
        return self.calcular_saldo_pendiente() <= 0
    
    def puede_entregar(self):
        """Verifica si el ticket puede ser entregado"""
        if self.estado != TicketEstados.LISTO:  # ✅ Usar constante
            return False, "El ticket no está listo para entrega"
        if not self.esta_pagado():
            return False, "El ticket tiene saldo pendiente de pago"
        return True, ""
    
    def marcar_como_entregado(self):
        """Marca el ticket como entregado"""
        puede, mensaje = self.puede_entregar()
        if not puede:
            raise ValueError(mensaje)
        
        self.estado = TicketEstados.ENTREGADO  # ✅ Usar constante
        self.fecha_entrega = timezone.now()
        self.save()


class TicketItem(AuditModel):
    """Items/Prendas dentro de un ticket"""
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Ticket"
    )
    
    servicio = models.ForeignKey(
        'servicios.Servicio',
        on_delete=models.PROTECT,
        verbose_name="Servicio"
    )
    
    prenda = models.ForeignKey(
        'servicios.Prenda',
        on_delete=models.PROTECT,
        verbose_name="Prenda",
        null=True,
        blank=True
    )
    
    cantidad = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=1, 
        verbose_name="Cantidad"
    )
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio Unitario"
    )
    
    descripcion = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Descripción"
    )
    
    # Estado individual del item
    completado = models.BooleanField(default=False, verbose_name="Completado")
    
    class Meta:
        verbose_name = "Item de Ticket"
        verbose_name_plural = "Items de Ticket"
        ordering = ['id']
    
    def __str__(self):
        return f"{self.servicio.nombre} - {self.prenda} x{self.cantidad}"
    
    @property
    def subtotal(self):
        if not self.cantidad or self.precio_unitario is None:
            return 0
        return self.cantidad * self.precio_unitario
    
    def save(self, *args, **kwargs):
        from .services import TicketService
        # Delegar cálculo de precio al servicio (SRP)
        TicketService.set_item_price(self)
        super().save(*args, **kwargs)


class EstadoHistorial(AuditModel):
    """Historial de cambios de estado de un ticket"""
    # Hereda de AuditModel para tener campos de auditoría y tenant
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='historial_estados',
        verbose_name="Ticket"
    )
    
    estado_anterior = models.CharField(max_length=20, verbose_name="Estado Anterior")
    estado_nuevo = models.CharField(max_length=20, verbose_name="Estado Nuevo")
    
    fecha_cambio = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Cambio")
    
    # 'usuario' ya viene incluido en AuditModel como 'creado_por', 
    # pero mantenemos 'usuario' explícito si tu lógica frontend lo usa así, 
    # o mejor usamos el AuditModel para estandarizar.
    # Para no romper compatibilidad, mantendremos la propiedad apuntando a creado_por
    
    comentario = models.TextField(blank=True, verbose_name="Comentario")
    
    class Meta:
        verbose_name = "Historial de Estado"
        verbose_name_plural = "Historial de Estados"
        ordering = ['-fecha_cambio']
    
    def __str__(self):
        return f"Ticket {self.ticket.numero_ticket}: {self.estado_anterior} → {self.estado_nuevo}"
    
    @property
    def usuario(self):
        return self.creado_por