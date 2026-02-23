from django.http import JsonResponse
from core.models import Sede
from django.utils.deprecation import MiddlewareMixin

class SedeContextMiddleware:
    """
    Middleware que establece la sede actual basado en el header X-Current-Sede-ID.
    
    Flujo:
    1. Lee X-Current-Sede-ID del header
    2. Valida que el usuario tenga acceso a esa sede
    3. Establece request.current_sede
    4. Si no hay header, usa sede por defecto del usuario
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Inicializar current_sede como None para evitar errores si no pasa por la lógica
        request.current_sede = None

        # Excluir rutas de autenticación y admin
        if request.path.startswith('/api/token/') or request.path.startswith('/admin/'):
            return self.get_response(request)

        # Solo para usuarios autenticados
        if request.user.is_authenticated and hasattr(request.user, 'perfil'):
            sede_id = request.headers.get('X-Current-Sede-ID')
            if sede_id:
                # Validar que la sede existe y pertenece a la empresa del usuario
                try:
                    sede = Sede.objects.get(
                        id=sede_id,
                        empresa=request.user.perfil.empresa,
                        activo=True
                    )
                    # Validar acceso
                    if request.user.perfil.puede_acceder_sede(sede):
                        request.current_sede = sede
                except (Sede.DoesNotExist, ValueError):
                    pass
            else:
                # Usar sede por defecto del usuario si no se especifica header
                # Si el usuario tiene una sede asignada en su perfil, usamos esa.
                if request.user.perfil.sede:
                    request.current_sede = request.user.perfil.sede
                
                # Si es un endpoint que requiere sede obligatoria, las vistas lo validarán.
                # Aquí solo establecemos el contexto si es posible.
        
        response = self.get_response(request)
        return response
