from django.db import models
from django.contrib.auth.models import User
from core.models import Empresa, Sede 

class PerfilUsuario(models.Model):
    ROLES = (
        ('ADMIN', 'Administrador'),
        ('CAJERO', 'Cajero'),
        ('OPERARIO', 'Operario'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='usuarios')
    sede = models.ForeignKey(
        Sede, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='usuarios_asignados',
        verbose_name='Sede Principal'
    )
    rol = models.CharField(max_length=20, choices=ROLES, default='OPERARIO')
    telefono = models.CharField(max_length=20, null=True, blank=True)
    
    # Control de acceso a múltiples sedes (Solo admins)
    sedes_permitidas = models.ManyToManyField(
        Sede,
        related_name='usuarios_permitidos',
        blank=True,
        verbose_name='Sedes Adicionales'
    )

    def __str__(self):
        return f"{self.user.username} - {self.rol}"

    def puede_acceder_sede(self, sede):
        """
        Verifica si el usuario tiene permiso para acceder a una sede explícita.
        - Si es la sede principal asignada: OK
        - Si es ADMIN y está en sedes_permitidas: OK
        """
        if not sede: 
            return False
            
        # Acceso directo a su sede principal
        if self.sede and self.sede.id == sede.id:
            return True
            
        # Si es admin, verificar que la sede pertenezca a su empresa
        if self.rol == 'ADMIN':
            return sede.empresa_id == self.empresa_id
            
        return False