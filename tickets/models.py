"""
Modelos para la gestión de tickets/órdenes de servicio
Actualizado para SaaS (Multi-tenant) con lógica de negocio completa
"""

from django.db import models
from django.contrib.auth.models import User
from core.models import AuditModel, SoftDeleteModel, Sede, Empresa, TimeStampedModel
from core.utils import generar_numero_unico, generar_qr_code
from django.utils import timezone


class ConfiguracionTicket(TimeStampedModel):
    """
    Configuración de tickets específica por Empresa
    """
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name='config_tickets')
    
    prefijo_ticket = models.CharField(max_length=5, default='TKT', verbose_name="Prefijo (Ej: TKT)")
    plazo_entrega_default = models.PositiveIntegerField(default=48, verbose_name="Plazo entrega default (horas)")
    
    terminos_condiciones = models.TextField(default="No nos hacemos responsables por prendas que destiñen...", verbose_name="Términos y Condiciones")
    pie_pagina_ticket = models.TextField(default="¡Gracias por su preferencia!", verbose_name="Pie de página del ticket")
    
    # Formato visual
    mostrar_precios_ticket = models.BooleanField(default=True)
    incluir_logo_ticket = models.BooleanField(default=True)

    def __str__(self):
        return f"Config Tickets - {self.empresa.nombre}"


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
        ]
    
    def __str__(self):
        return f"{self.nombres} {self.apellidos} - {self.numero_documento}"
    
    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".strip()
    
    def total_gastado(self):
        """Calcula el total gastado por el cliente"""
        from pagos.models import Pago
        return Pago.objects.filter(
            ticket__cliente=self,
            estado='PAGADO'
        ).aggregate(total=models.Sum('monto'))['total'] or 0


class Ticket(AuditModel, SoftDeleteModel):
    """Modelo principal de Ticket/Orden de Servicio (SaaS)"""
    
    ESTADO_CHOICES = [
        ('RECIBIDO', 'Recibido'),
        ('EN_PROCESO', 'En Proceso'),
        ('LISTO', 'Listo para Entrega'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    PRIORIDAD_CHOICES = [
        ('NORMAL', 'Normal'),
        ('URGENTE', 'Urgente'),
        ('EXPRESS', 'Express'),
    ]

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

    qr_code = models.ImageField(
        upload_to='tickets/qr/',
        blank=True,
        null=True,
        verbose_name="Código QR"
    )
    
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
        default='RECIBIDO',
        verbose_name="Estado"
    )
    prioridad = models.CharField(
        max_length=20,
        choices=PRIORIDAD_CHOICES,
        default='NORMAL',
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
    instrucciones_especiales = models.TextField(blank=True, verbose_name="Instrucciones Especiales")
    
    requiere_pago_anticipado = models.BooleanField(default=False, verbose_name="Requiere Pago Anticipado")
    
    empleado_asignado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets_asignados',
        verbose_name="Empleado Asignado"
    )
    
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
        # LÓGICA SAAS: Generar número usando configuración de empresa
        if not self.numero_ticket and self.empresa:
            try:
                # Intentamos obtener config, si no existe usamos default
                config = self.empresa.config_tickets
                prefijo = config.prefijo_ticket
            except:
                prefijo = 'TKT'
            
            # Buscamos el último secuencial de ESTA empresa
            ultimo = Ticket.objects.filter(empresa=self.empresa).order_by('-secuencial').first()
            nuevo_sec = (ultimo.secuencial + 1) if ultimo else 1
            self.secuencial = nuevo_sec
            
            # Formato: PREFIJO-AÑO-SECUENCIAL (Ej: WASH-2024-0001)
            anio = timezone.now().year
            self.numero_ticket = f"{prefijo}-{anio}-{str(nuevo_sec).zfill(6)}"
        
        # Fallback por si acaso falla la lógica anterior o no hay empresa (casos edge)
        if not self.numero_ticket:
             self.numero_ticket = generar_numero_unico(prefijo='TKT')

        # Generar código QR si no existe
        if not self.qr_code:
            qr_data = f"WASHLY|{self.numero_ticket}|{self.id}"
            self.qr_code = generar_qr_code(qr_data, filename=f'ticket_{self.numero_ticket}')
        
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
        if self.estado != 'LISTO':
            return False, "El ticket no está listo para entrega"
        if not self.esta_pagado() and not self.requiere_pago_anticipado:
            return False, "El ticket tiene saldo pendiente de pago"
        return True, ""
    
    def marcar_como_entregado(self):
        """Marca el ticket como entregado"""
        puede, mensaje = self.puede_entregar()
        if not puede:
            raise ValueError(mensaje)
        
        self.estado = 'ENTREGADO'
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
        # Lógica original para determinar precio
        if not self.precio_unitario and self.servicio:
            if self.prenda:
                # Buscar precio específico de servicio-prenda
                precio_especifico = self.servicio.precios_prendas.filter(
                    prenda=self.prenda
                ).first()
                if precio_especifico:
                    self.precio_unitario = precio_especifico.precio
                else:
                    self.precio_unitario = self.servicio.precio_base
            else:
                self.precio_unitario = self.servicio.precio_base
        
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