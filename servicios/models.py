"""
Modelos para la gestión de servicios de lavandería
"""

from django.db import models
from core.models import AuditModel, SoftDeleteModel, Sede


class CategoriaServicio(AuditModel, SoftDeleteModel):
    """Categorías de servicios (lavado, planchado, etc.)"""
    
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    icono = models.CharField(max_length=50, blank=True, verbose_name="Icono")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden de visualización")
    
    class Meta:
        verbose_name = "Categoría de Servicio"
        verbose_name_plural = "Categorías de Servicios"
        ordering = ['orden', 'nombre']
    
    def __str__(self):
        return self.nombre


class Servicio(AuditModel, SoftDeleteModel):
    """Servicios ofrecidos por la lavandería"""
    
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Servicio")
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    
    categoria = models.ForeignKey(
        CategoriaServicio,
        on_delete=models.PROTECT,
        related_name='servicios',
        verbose_name="Categoría"
    )
    
    # Precios
    precio_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio Base"
    )
    
    # Tiempo estimado en minutos
    tiempo_estimado = models.PositiveIntegerField(
        default=60,
        verbose_name="Tiempo Estimado (minutos)"
    )
    
    # Configuración
    requiere_prenda = models.BooleanField(
        default=True,
        verbose_name="Requiere especificar prenda"
    )
    disponible = models.BooleanField(default=True, verbose_name="Disponible")
    
    # Sedes donde está disponible
    sedes = models.ManyToManyField(
        Sede,
        related_name='servicios_disponibles',
        blank=True,
        verbose_name="Sedes donde está disponible"
    )
    
    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        ordering = ['categoria', 'nombre']
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['categoria', 'disponible']),
        ]
    
    def __str__(self):
        return f"{self.nombre} - S/ {self.precio_base}"


class TipoPrenda(AuditModel, SoftDeleteModel):
    """Tipos de prendas (camisa, pantalón, etc.)"""
    
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    icono = models.CharField(max_length=50, blank=True, verbose_name="Icono")
    
    class Meta:
        verbose_name = "Tipo de Prenda"
        verbose_name_plural = "Tipos de Prendas"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Prenda(AuditModel, SoftDeleteModel):
    """Prendas específicas"""
    
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    tipo = models.ForeignKey(
        TipoPrenda,
        on_delete=models.PROTECT,
        related_name='prendas',
        verbose_name="Tipo de Prenda"
    )
    
    # Multiplicador de precio (opcional)
    multiplicador_precio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        verbose_name="Multiplicador de Precio"
    )
    
    class Meta:
        verbose_name = "Prenda"
        verbose_name_plural = "Prendas"
        ordering = ['tipo', 'nombre']
    
    def __str__(self):
        return f"{self.tipo.nombre} - {self.nombre}"


class PrecioPorPrenda(AuditModel):
    """Precios específicos de servicio por tipo de prenda"""
    
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name='precios_prendas',
        verbose_name="Servicio"
    )
    prenda = models.ForeignKey(
        Prenda,
        on_delete=models.CASCADE,
        related_name='precios_servicios',
        verbose_name="Prenda"
    )
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio"
    )
    
    class Meta:
        verbose_name = "Precio por Prenda"
        verbose_name_plural = "Precios por Prenda"
        unique_together = ['servicio', 'prenda']
        ordering = ['servicio', 'prenda']
    
    def __str__(self):
        return f"{self.servicio.nombre} - {self.prenda.nombre}: S/ {self.precio}"


class Promocion(AuditModel, SoftDeleteModel):
    """Promociones y combos"""
    
    TIPO_CHOICES = [
        ('DESCUENTO_PORCENTAJE', 'Descuento en Porcentaje'),
        ('DESCUENTO_MONTO', 'Descuento en Monto Fijo'),
        ('COMBO', 'Combo de Servicios'),
        ('2X1', '2x1'),
        ('PRECIO_FIJO', 'Precio Fijo'),
    ]
    
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la Promoción")
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    descripcion = models.TextField(verbose_name="Descripción")
    
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, verbose_name="Tipo de Promoción")
    
    # Valor del descuento
    valor_descuento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor del Descuento"
    )
    
    # Servicios incluidos
    servicios = models.ManyToManyField(
        Servicio,
        related_name='promociones',
        verbose_name="Servicios Incluidos"
    )
    
    # Validez
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de Fin")
    
    # Condiciones
    monto_minimo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Monto Mínimo de Compra"
    )
    cantidad_minima = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Cantidad Mínima de Items"
    )
    
    # Estado
    activa = models.BooleanField(default=True, verbose_name="Activa")
    usos_maximos = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Usos Máximos"
    )
    usos_actuales = models.PositiveIntegerField(default=0, verbose_name="Usos Actuales")
    
    class Meta:
        verbose_name = "Promoción"
        verbose_name_plural = "Promociones"
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return f"{self.nombre} ({self.codigo})"
    
    def es_valida(self):
        """Verifica si la promoción es válida"""
        from django.utils import timezone
        hoy = timezone.now().date()
        
        if not self.activa or not self.activo:
            return False
        
        if hoy < self.fecha_inicio or hoy > self.fecha_fin:
            return False
        
        if self.usos_maximos and self.usos_actuales >= self.usos_maximos:
            return False
        
        return True
    
    def calcular_descuento(self, subtotal):
        """Calcula el descuento a aplicar"""
        if not self.es_valida():
            return 0
        
        if self.tipo == 'DESCUENTO_PORCENTAJE':
            return subtotal * (self.valor_descuento / 100)
        elif self.tipo == 'DESCUENTO_MONTO':
            return min(self.valor_descuento, subtotal)
        elif self.tipo == 'PRECIO_FIJO':
            return max(0, subtotal - self.valor_descuento)
        
        return 0
