from django.db import models
from django.contrib.auth.models import User
from core.models import Empresa, TimeStampedModel

class PerfilUsuario(TimeStampedModel):
    """
    Extensión del usuario para manejar Roles y Multi-tenant
    """
    ROLES = [
        ('ADMIN_NEGOCIO', 'Administrador del Negocio'), # Dueño, acceso a todo config
        ('GERENTE_SEDE', 'Gerente de Sede'), # Acceso a reportes de su sede
        ('CAJERO', 'Cajero'), # Acceso a POS y Pagos
        ('OPERARIO', 'Operario de Lavandería'), # Solo cambio de estados de tickets
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='colaboradores')
    
    rol = models.CharField(max_length=20, choices=ROLES, default='OPERARIO')
    
    # Si es null, tiene acceso a todas (solo para ADMIN_NEGOCIO)
    sedes_permitidas = models.ManyToManyField('core.Sede', blank=True, related_name='usuarios_permitidos')
    
    telefono = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.get_rol_display()}"

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"