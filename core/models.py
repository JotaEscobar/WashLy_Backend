"""
Modelos abstractos base para el sistema ERP Washly
Actualizado para soporte SaaS (Multi-tenant)
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class Empresa(models.Model):
    """
    Modelo Tenant (Empresa/Cliente SaaS)
    """
    PLANES = [
        ('FREE', 'Plan Gratuito / Prueba'),
        ('PRO', 'Plan Profesional'),
        ('ENTERPRISE', 'Plan Empresarial'),
    ]

    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('SUSPENDIDO', 'Suspendido (Falta de pago)'),
        ('INACTIVO', 'Inactivo (Baja)'),
    ]

    # Configuración General del Negocio
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Negocio")
    logo = models.ImageField(upload_to='logos_empresas/', null=True, blank=True, verbose_name="Logo")
    ruc = models.CharField(max_length=20, verbose_name="RUC / ID Fiscal", unique=True)
    direccion_fiscal = models.TextField(verbose_name="Dirección Fiscal", blank=True)
    telefono_contacto = models.CharField(max_length=20, verbose_name="Teléfono de Contacto", blank=True)
    email_contacto = models.EmailField(verbose_name="Email de Contacto", blank=True)
    
    # Configuración Regional
    zona_horaria = models.CharField(max_length=50, default='America/Lima', verbose_name="Zona Horaria")
    moneda = models.CharField(max_length=3, default='PEN', verbose_name="Moneda (ISO)")

    # Campos SaaS
    plan = models.CharField(max_length=20, choices=PLANES, default='FREE')
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateTimeField(verbose_name="Fecha de Vencimiento")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVO')

    # --- NUEVO: Configuración de Tickets ---
    ticket_prefijo = models.CharField(max_length=10, default='TK-', verbose_name="Prefijo del Ticket")
    ticket_dias_entrega = models.PositiveIntegerField(default=2, verbose_name="Días defecto para entrega")
    ticket_mensaje_pie = models.TextField(blank=True, verbose_name="Mensaje al pie del ticket")

    # Configuración Global de Inventario y Notificaciones
    stock_minimo_global = models.PositiveIntegerField(default=10, verbose_name="Alerta Stock Mínimo Global")
    
    # Toggles de Notificaciones (Globales por empresa)
    notif_email_activas = models.BooleanField(default=True, verbose_name="Activar Email")
    notif_whatsapp_activas = models.BooleanField(default=False, verbose_name="Activar WhatsApp")
    notif_sms_activas = models.BooleanField(default=False, verbose_name="Activar SMS")

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        # Lógica: Al crear, dar 7 días de prueba si no se especifica fecha
        if not self.pk and not self.fecha_vencimiento:
            self.fecha_vencimiento = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def es_valida(self):
        return self.estado == 'ACTIVO' and self.fecha_vencimiento > timezone.now()


class TimeStampedModel(models.Model):
    """
    Modelo abstracto que añade campos de timestamp
    """
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    
    class Meta:
        abstract = True


class TenantModel(models.Model):
    """
    Modelo abstracto para vincular datos a una Empresa (SaaS).
    Todo modelo que herede de esto pertenecerá a una empresa específica.
    """
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        related_name="%(app_label)s_%(class)s_items",
        verbose_name="Empresa"
    )

    class Meta:
        abstract = True


class AuditModel(TimeStampedModel, TenantModel):
    """
    Modelo abstracto que añade auditoría de usuarios y vinculación a Empresa.
    Reemplaza al AuditModel anterior añadiendo 'TenantModel'.
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
    Modelo para manejar sucursales de una Empresa
    """
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la sede")
    codigo = models.CharField(max_length=20, verbose_name="Código Interno") 
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
        # El código debe ser único SOLO dentro de la misma empresa
        unique_together = ['empresa', 'codigo']
    
    def __str__(self):
        return f"{self.nombre} ({self.codigo})"