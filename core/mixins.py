"""
Mixins compartidos para Views DRF.

IMPORTANTE: La resolución de sede se hace aquí (view layer) porque el middleware
de Django ejecuta ANTES de que DRF autentique el JWT. En el middleware,
request.user es AnonymousUser para JWT, así que la lógica de sede se salta.
Al resolver aquí, DRF ya autenticó al usuario y request.user está disponible.
"""

from core.models import Sede


def resolver_sede_desde_request(request):
    """
    Resuelve la sede actual desde el header X-Current-Sede-ID.
    Debe llamarse SOLO después de que DRF haya autenticado al usuario
    (es decir, dentro de views/viewsets, NO en middleware).
    
    Returns: Sede instance o None
    """
    # Si el middleware ya resolvió (ej: sesión Django), usar eso
    if hasattr(request, 'current_sede') and request.current_sede:
        return request.current_sede
    
    # Resolver desde header (caso JWT donde middleware no pudo resolver)
    sede_id = request.headers.get('X-Current-Sede-ID')
    
    if sede_id and hasattr(request.user, 'perfil'):
        try:
            sede = Sede.objects.get(
                id=sede_id,
                empresa=request.user.perfil.empresa,
                activo=True
            )
            # Validar acceso
            if request.user.perfil.puede_acceder_sede(sede):
                # Cache en el request para no repetir la query
                request.current_sede = sede
                return sede
        except (Sede.DoesNotExist, ValueError):
            pass
    
    # Fallback: sede del perfil del usuario
    if hasattr(request.user, 'perfil') and request.user.perfil.sede:
        request.current_sede = request.user.perfil.sede
        return request.user.perfil.sede
    
    return None
