"""
Modelos abstractos base para el sistema ERP Washly
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Modelo abstracto que añade campos de timestamp
    """
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    
    class Meta:
        abstract = True


class AuditModel(TimeStampedModel):
    """
    Modelo abstracto que añade auditoría de usuarios
    """
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_creados",
        verbose_name="Creado por"
    )
    actualizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_actualizados",
        verbose_name="Actualizado por"
    )
    
    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Modelo abstracto para soft delete
    """
    activo = models.BooleanField(default=True, verbose_name="Activo")
    eliminado_en = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de eliminación")
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        """Marca el registro como eliminado"""
        self.activo = False
        self.eliminado_en = timezone.now()
        self.save()
    
    def restore(self):
        """Restaura un registro eliminado"""
        self.activo = True
        self.eliminado_en = None
        self.save()


class Sede(AuditModel, SoftDeleteModel):
    """
    Modelo para manejar múltiples sedes (multi-tenant)
    """
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la sede")
    codigo = models.CharField(max_length=20, unique=True, verbose_name="Código")
    direccion = models.TextField(verbose_name="Dirección")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    email = models.EmailField(verbose_name="Email")
    
    # Configuración de la sede
    horario_apertura = models.TimeField(verbose_name="Horario de apertura")
    horario_cierre = models.TimeField(verbose_name="Horario de cierre")
    
    class Meta:
        verbose_name = "Sede"
        verbose_name_plural = "Sedes"
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.codigo})"
