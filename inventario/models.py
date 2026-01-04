"""
Modelos para gestión de inventario
"""

from django.db import models
from django.core.exceptions import ValidationError
from core.models import AuditModel, SoftDeleteModel, Sede


class CategoriaProducto(AuditModel, SoftDeleteModel):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Categoría de Producto"
        verbose_name_plural = "Categorías de Productos"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Producto(AuditModel, SoftDeleteModel):
    UNIDAD_MEDIDA_CHOICES = [
        ('UND', 'Unidad'),
        ('KG', 'Kilogramo'),
        ('L', 'Litro'),
        ('ML', 'Mililitro'),
        ('GR', 'Gramo'),
        ('CAJA', 'Caja'),
        ('PAQUETE', 'Paquete'),
    ]
    
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)
    categoria = models.ForeignKey(CategoriaProducto, on_delete=models.PROTECT, related_name='productos')
    
    unidad_medida = models.CharField(max_length=20, choices=UNIDAD_MEDIDA_CHOICES)
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2)
    stock_maximo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='productos', null=True, blank=True)
    
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['stock_actual', 'stock_minimo']),
        ]
    
    def __str__(self):
        return f"{self.nombre} ({self.codigo})"
    
    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo
    
    @property
    def stock_critico(self):
        return self.stock_actual <= (self.stock_minimo * 0.5)


class MovimientoInventario(AuditModel):
    TIPO_MOVIMIENTO_CHOICES = [
        ('ENTRADA', 'Entrada'),
        ('SALIDA', 'Salida'),
        ('AJUSTE', 'Ajuste'),
        ('TRANSFERENCIA', 'Transferencia'),
    ]
    
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    stock_anterior = models.DecimalField(max_digits=10, decimal_places=2)
    stock_nuevo = models.DecimalField(max_digits=10, decimal_places=2)
    
    motivo = models.TextField()
    documento_referencia = models.CharField(max_length=100, blank=True)
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ['-creado_en']
    
    def __str__(self):
        return f"{self.tipo} - {self.producto.nombre} - {self.cantidad}"
    
    def save(self, *args, **kwargs):
        if not self.pk:  # Solo en creación
            self.stock_anterior = self.producto.stock_actual
            
            if self.tipo == 'ENTRADA':
                self.producto.stock_actual += self.cantidad
            elif self.tipo == 'SALIDA':
                if self.producto.stock_actual < self.cantidad:
                    raise ValidationError('Stock insuficiente')
                self.producto.stock_actual -= self.cantidad
            elif self.tipo == 'AJUSTE':
                self.producto.stock_actual = self.cantidad
            
            self.stock_nuevo = self.producto.stock_actual
            self.producto.save()
        
        super().save(*args, **kwargs)


class AlertaStock(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='alertas')
    fecha_alerta = models.DateTimeField(auto_now_add=True)
    nivel = models.CharField(max_length=20, choices=[('BAJO', 'Bajo'), ('CRITICO', 'Crítico')])
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2)
    resuelta = models.BooleanField(default=False)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Alerta de Stock"
        verbose_name_plural = "Alertas de Stock"
        ordering = ['-fecha_alerta']
    
    def __str__(self):
        return f"Alerta {self.nivel} - {self.producto.nombre}"
