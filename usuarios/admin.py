from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import PerfilUsuario

# Definimos el Perfil como un bloque "en línea" dentro del Usuario
class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfil de Usuario (Configuración SaaS)'
    fk_name = 'user'

# Extendemos el Admin de Usuario original
class UserAdmin(BaseUserAdmin):
    inlines = (PerfilUsuarioInline,)
    
    # Agregamos columnas personalizadas a la lista de usuarios
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_empresa', 'get_rol')
    
    # Funciones para mostrar datos del perfil en la tabla
    def get_empresa(self, obj):
        return obj.perfil.empresa.nombre if hasattr(obj, 'perfil') and obj.perfil.empresa else '-'
    get_empresa.short_description = 'Empresa Asignada'

    def get_rol(self, obj):
        return obj.perfil.rol if hasattr(obj, 'perfil') else '-'
    get_rol.short_description = 'Rol'

# Desregistramos el User original y registramos el nuestro vitaminado
admin.site.unregister(User)
admin.site.register(User, UserAdmin)