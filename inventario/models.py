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
        ('GALON', 'Galón'),
        ('BIDON', 'Bidón'),
    ]
    
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)
    categoria = models.ForeignKey(CategoriaProducto, on_delete=models.PROTECT, related_name='productos')
    
    unidad_medida = models.CharField(max_length=20, choices=UNIDAD_MEDIDA_CHOICES)
    
    # Stocks
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    
    # Precio Referencial (Última compra)
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='productos', null=True, blank=True)
    
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.stock_actual} {self.unidad_medida})"
    
    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo

class MovimientoInventario(AuditModel):
    TIPO_MOVIMIENTO_CHOICES = [
        ('COMPRA', 'Compra / Entrada'),       # Aumenta Stock
        ('CONSUMO', 'Consumo Interno'),       # Disminuye Stock
        ('AJUSTE', 'Ajuste de Inventario'),   # Resetea Stock (Corrección física)
    ]
    
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cantidad a mover o nuevo stock si es ajuste")
    
    # Auditoría de stocks
    stock_anterior = models.DecimalField(max_digits=10, decimal_places=2)
    stock_nuevo = models.DecimalField(max_digits=10, decimal_places=2)
    
    motivo = models.TextField(blank=True)
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Solo para compras")
    
    class Meta:
        ordering = ['-creado_en']
        
    def save(self, *args, **kwargs):
        if not self.pk:
            self.stock_anterior = self.producto.stock_actual
            
            if self.tipo == 'COMPRA':
                self.producto.stock_actual += self.cantidad
                # Actualizamos el precio de referencia del producto
                if self.costo_unitario:
                    self.producto.precio_compra = self.costo_unitario
                    
            elif self.tipo == 'CONSUMO':
                if self.producto.stock_actual < self.cantidad:
                    raise ValidationError(f"Stock insuficiente. Tienes {self.producto.stock_actual} y quieres consumir {self.cantidad}")
                self.producto.stock_actual -= self.cantidad
                
            elif self.tipo == 'AJUSTE':
                self.producto.stock_actual = self.cantidad
            
            self.stock_nuevo = self.producto.stock_actual
            self.producto.save()
            
        super().save(*args, **kwargs)

class AlertaStock(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    mensaje = models.CharField(max_length=255)