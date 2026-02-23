"""
Servicios para la gestión de usuarios
Centraliza lógica de negocio fuera de serializers/views
"""
from django.contrib.auth.models import User
from .models import PerfilUsuario


class UserService:
    """Servicio para operaciones de usuarios y perfiles"""
    
    @staticmethod
    def create_user_with_profile(first_name, last_name, email, password, empresa, rol, sede=None, created_by=None):
        """
        Crea un usuario Django y su perfil asociado
        
        Args:
            first_name (str): Nombre del usuario
            last_name (str): Apellido del usuario
            email (str): Email del usuario
            password (str): Contraseña
            empresa (Empresa): Empresa a la que pertenece
            rol (str): Rol del usuario (ADMIN, CAJERO, OPERARIO)
            sede (Sede, optional): Sede asignada
            created_by (User, optional): Usuario que crea este registro
            
        Returns:
            User: El usuario creado con su perfil
            
        Raises:
            ValueError: Si hay problemas en la creación
        """
        # 1. Generar username único
        username = UserService._generate_unique_username(first_name, last_name)
        
        # 2. Crear usuario Django
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email
        )
        
        # 3. Crear perfil (✅ usando 'user' no 'usuario')
        PerfilUsuario.objects.create(
            user=user,  # ✅ Nombre correcto del campo
            empresa=empresa,
            rol=rol,
            sede=sede
        )
        
        return user
    
    @staticmethod
    def _generate_unique_username(first_name, last_name):
        """
        Genera un username único basado en nombre y apellido
        Formato: primera_letra_nombre + apellido (ej: jperez)
        Si existe, agrega un contador (jperez1, jperez2, etc.)
        """
        # Generar nombre base
        base_username = f"{first_name[0]}{last_name}".lower().replace(" ", "")
        username = base_username
        counter = 1
        
        # Buscar username disponible
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        return username
    
    @staticmethod
    def update_user_profile(user, rol=None, sede=None, updated_by=None):
        """
        Actualiza el perfil de un usuario existente
        
        Args:
            user (User): Usuario a actualizar
            rol (str, optional): Nuevo rol
            sede (Sede, optional): Nueva sede (puede ser None)
            updated_by (User, optional): Usuario que realiza la actualización
        """
        perfil = user.perfil
        
        if rol is not None:
            perfil.rol = rol
        
        # Permitir actualizar sede a None
        if sede is not None or 'sede' in locals():
            perfil.sede = sede
        
        perfil.save()
        return perfil
