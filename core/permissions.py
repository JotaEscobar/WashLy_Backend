from rest_framework import permissions
from django.utils import timezone

class IsActiveSubscription(permissions.BasePermission):
    """
    GLOBAL KILL-SWITCH:
    Bloquea CUALQUIER petición si la fecha de vencimiento de la empresa ha pasado.
    Excepción: Permite peticiones a endpoints de 'pagos' para renovar.
    """
    message = "Su suscripción ha vencido. Por favor renueve su servicio."

    def has_permission(self, request, view):
        # 1. Verificar autenticación básica
        if not request.user or not request.user.is_authenticated:
            return False

        # 2. Permitir acceso a superusuarios (opcional, para soporte)
        if request.user.is_superuser:
            return True

        # 3. Whitelist: Endpoints de pagos siempre permitidos
        # Asume que tus URLs de pagos contienen 'pagos' o usas un namespace específico
        path = request.path_info.lower()
        if 'pagos' in path or 'webhook' in path:
            return True

        # 4. Verificar Fecha de Vencimiento
        try:
            empresa = request.user.perfil.empresa
            if empresa.fecha_vencimiento < timezone.now().date():
                return False # 403 Forbidden
        except AttributeError:
            # Usuario sin perfil/empresa configurada correctamente
            return False
            
        return True

class IsAdminUser(permissions.BasePermission):
    """Acceso total para dueños/admins"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.perfil.rol == 'ADMIN'

class IsCashierUser(permissions.BasePermission):
    """
    Acceso para Cajeros y Admins (Jerárquico).
    Permite POS, Clientes, Pagos, Ver Tickets.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.perfil.rol in ['ADMIN', 'CAJERO']

class IsOperarioUser(permissions.BasePermission):
    """
    Acceso estricto para Operarios.
    Generalmente solo ver/actualizar estado de tickets.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # Nota: El Admin suele poder hacer todo lo que el operario hace
        return request.user.perfil.rol in ['ADMIN', 'OPERARIO']