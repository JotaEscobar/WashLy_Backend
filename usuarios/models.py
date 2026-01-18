from django.db import models
from django.contrib.auth.models import User
from core.models import Empresa, Sede, TimeStampedModel

class PerfilUsuario(TimeStampedModel):
    """
    Extensión del usuario para manejar Roles y Multi-tenant
    """
    ROLES = [
        ('ADMIN', 'Administrador del Negocio'), # Acceso total
        ('CAJERO', 'Cajero / Ventas'),          # Acceso a POS, Cortes de Caja
        ('OPERARIO', 'Operario de Planta'),     # Solo gestión de Tickets/Procesos
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='colaboradores')
    
    # ForeignKey opcional: Si es null, tiene acceso global (útil para Admins o Supervisores)
    # Si tiene valor, el frontend/backend puede restringir la info solo a esa sede.
    sede = models.ForeignKey(Sede, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios_asignados', verbose_name="Sede Asignada")
    
    rol = models.CharField(max_length=20, choices=ROLES, default='OPERARIO')
    telefono = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.get_rol_display()}"

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"