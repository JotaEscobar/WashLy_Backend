"""
Modelos para la gestión de servicios de lavandería
Actualizado para SaaS y corrección de lógica de precios por prenda
"""

from django.db import models
from core.models import AuditModel, SoftDeleteModel, Sede

class CategoriaServicio(AuditModel, SoftDeleteModel):
    """
    Categorías de servicios (Ej: Lavado por Kilo, Lavado por Prenda/Sastrería, Zapatillas)
    """
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    icono = models.CharField(max_length=50, blank=True, verbose_name="Icono (React/Phosphor)")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden de visualización")
    
    class Meta:
        verbose_name = "Categoría de Servicio"
        verbose_name_plural = "Categorías de Servicios"
        ordering = ['orden', 'nombre']
        # El nombre debe ser único solo dentro de la misma empresa
        unique_together = ['empresa', 'nombre']
    
    def __str__(self):
        return self.nombre


class TipoPrenda(AuditModel, SoftDeleteModel):
    """
    Agrupación de prendas (Ej: Ropa de Cama, Ropa de Vestir, Accesorios)
    Ayuda a filtrar el selector de prendas en el POS.
    """
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    icono = models.CharField(max_length=50, blank=True, verbose_name="Icono")
    
    class Meta:
        verbose_name = "Tipo de Prenda"
        verbose_name_plural = "Tipos de Prendas"
        ordering = ['nombre']
        unique_together = ['empresa', 'nombre']
    
    def __str__(self):
        return self.nombre


class Prenda(AuditModel, SoftDeleteModel):
    """
    Prendas específicas (Ej: Camisa, Pantalón, Edredón 2 Plazas)
    """
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    tipo = models.ForeignKey(
        TipoPrenda,
        on_delete=models.PROTECT,
        related_name='prendas',
        verbose_name="Tipo de Prenda"
    )
    
    # Multiplicador opcional (Ej: 1.5 para prendas de seda/delicadas si se requiere lógica compleja)
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
        unique_together = ['empresa', 'nombre', 'tipo']
    
    def __str__(self):
        return f"{self.tipo.nombre} - {self.nombre}"


class Servicio(AuditModel, SoftDeleteModel):
    """
    Servicios ofrecidos (Ej: Lavado Seco, Lavado Normal, Planchado)
    """
    
    TIPOS_COBRO = [
        ('POR_UNIDAD', 'Precio Fijo por Unidad (Ej: Lavado de Alfombra m2)'),
        ('POR_KILO', 'Precio por Peso/Kilo (Ej: Lavado Diario)'),
        ('POR_PRENDA', 'Precio dependiente de la Prenda (Ej: Sastrería/Dry Clean)'),
    ]

    nombre = models.CharField(max_length=200, verbose_name="Nombre del Servicio")
    codigo = models.CharField(max_length=50, verbose_name="Código")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    
    categoria = models.ForeignKey(
        CategoriaServicio,
        on_delete=models.PROTECT,
        related_name='servicios',
        verbose_name="Categoría"
    )
    
    # Lógica de Cobro
    tipo_cobro = models.CharField(
        max_length=20, 
        choices=TIPOS_COBRO, 
        default='POR_UNIDAD',
        verbose_name="Tipo de Cobro"
    )

    # Precio Base:
    # - Si es POR_UNIDAD: Es el precio del servicio.
    # - Si es POR_KILO: Es el precio del Kg.
    # - Si es POR_PRENDA: Es un precio "desde" referencial (el precio real sale de PrecioPorPrenda).
    precio_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Precio Base / Referencial"
    )
    
    # Configuración
    tiempo_estimado = models.PositiveIntegerField(
        default=24,
        verbose_name="Tiempo Estimado (horas)"
    )
    
    requiere_prenda = models.BooleanField(
        default=False,
        verbose_name="¿Requiere especificar prenda?"
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
        unique_together = ['empresa', 'codigo'] # Código único por empresa
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['categoria', 'disponible']),
        ]
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_cobro_display()})"
    
    def save(self, *args, **kwargs):
        # Si el tipo de cobro es POR_PRENDA, forzamos requiere_prenda a True
        if self.tipo_cobro == 'POR_PRENDA':
            self.requiere_prenda = True
        super().save(*args, **kwargs)


class PrecioPorPrenda(AuditModel):
    """
    Tabla de Precios Específicos:
    Define cuánto cuesta el Servicio X para la Prenda Y.
    Ej: Servicio="Lavado Seco" + Prenda="Camisa" = S/ 15.00
        Servicio="Lavado Seco" + Prenda="Terno" = S/ 35.00
    """
    
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
        verbose_name="Precio Final"
    )
    
    class Meta:
        verbose_name = "Precio por Prenda"
        verbose_name_plural = "Precios por Prenda"
        unique_together = ['servicio', 'prenda'] # Un solo precio por combinación
        ordering = ['servicio', 'prenda']
    
    def __str__(self):
        return f"{self.servicio.nombre} - {self.prenda.nombre}: S/ {self.precio}"


class Promocion(AuditModel, SoftDeleteModel):
    """Promociones y combos (Versión SaaS)"""
    
    TIPO_CHOICES = [
        ('DESCUENTO_PORCENTAJE', 'Descuento en Porcentaje'),
        ('DESCUENTO_MONTO', 'Descuento en Monto Fijo'),
        ('COMBO', 'Combo de Servicios'),
        ('2X1', '2x1'),
        ('PRECIO_FIJO', 'Precio Fijo'),
    ]
    
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la Promoción")
    codigo = models.CharField(max_length=50, verbose_name="Código")
    descripcion = models.TextField(verbose_name="Descripción")
    
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, verbose_name="Tipo de Promoción")
    
    valor_descuento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor del Descuento"
    )
    
    servicios = models.ManyToManyField(
        Servicio,
        related_name='promociones',
        verbose_name="Servicios Incluidos"
    )
    
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de Fin")
    
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
        unique_together = ['empresa', 'codigo'] # Código único por empresa
    
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