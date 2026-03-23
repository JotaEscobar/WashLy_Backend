from rest_framework import permissions
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


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

        # 2. Permitir acceso a superusuarios
        if request.user.is_superuser:
            return True

        # 3. Whitelist: Endpoints de pagos siempre permitidos
        path = request.path_info.lower()
        if 'pagos' in path or 'webhook' in path:
            return True

        # 4. Validación segura: Verificar que el usuario tiene perfil
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None:
            logger.warning(f"Usuario {request.user.id} sin perfil intentó acceder a {path}")
            return False

        # 5. Verificar Fecha de Vencimiento
        try:
            empresa = perfil.empresa
            if empresa is None:
                return False
            if empresa.fecha_vencimiento.date() < timezone.now().date():
                logger.info(f"Suscripción vencida para empresa {empresa.id}: {empresa.nombre}")
                return False
        except (AttributeError, TypeError):
            return False
            
        return True


class IsAdminUser(permissions.BasePermission):
    """Acceso total para dueños/admins"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        perfil = getattr(request.user, 'perfil', None)
        return perfil is not None and perfil.rol == 'ADMIN'


class IsCashierUser(permissions.BasePermission):
    """
    Acceso para Cajeros y Admins (Jerárquico).
    Permite POS, Clientes, Pagos, Ver Tickets.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        perfil = getattr(request.user, 'perfil', None)
        return perfil is not None and perfil.rol in ['ADMIN', 'CAJERO']


class IsOperarioUser(permissions.BasePermission):
    """
    Acceso estricto para Operarios.
    Generalmente solo ver/actualizar estado de tickets.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        perfil = getattr(request.user, 'perfil', None)
        return perfil is not None and perfil.rol in ['ADMIN', 'OPERARIO']