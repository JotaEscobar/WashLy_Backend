"""
URLs principales de Washly
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

# Importar viewsets
from tickets.views import ClienteViewSet, TicketViewSet, TicketItemViewSet
from servicios.views import (
    CategoriaServicioViewSet, ServicioViewSet, TipoPrendaViewSet,
    PrendaViewSet, PromocionViewSet
)
from core.views import EmpresaViewSet, SedeViewSet

# Router principal
router = DefaultRouter()

# Core (SaaS)
router.register(r'core/empresa', EmpresaViewSet, basename='empresa')
router.register(r'core/sedes', SedeViewSet, basename='sede')

# Registrar rutas de tickets
router.register(r'clientes', ClienteViewSet, basename='cliente')
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'ticket-items', TicketItemViewSet, basename='ticketitem')

# Registrar rutas de servicios
router.register(r'categorias-servicio', CategoriaServicioViewSet, basename='categoria-servicio')
router.register(r'servicios', ServicioViewSet, basename='servicio')
router.register(r'tipos-prenda', TipoPrendaViewSet, basename='tipo-prenda')
router.register(r'prendas', PrendaViewSet, basename='prenda')
router.register(r'promociones', PromocionViewSet, basename='promocion')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Authentication
    path('api/auth/login/', obtain_auth_token, name='api_token_auth'),
    
    # API Routes
    path('api/', include(router.urls)),
    
    # Apps URLs
    path('api/inventario/', include('inventario.urls')),
    path('api/pagos/', include('pagos.urls')),
    path('api/notificaciones/', include('notificaciones.urls')),
    path('api/reportes/', include('reportes.urls')),
]

# Servir archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Configurar títulos del admin
admin.site.site_header = "Washly - Sistema ERP"
admin.site.site_title = "Washly Admin"
admin.site.index_title = "Panel de Administración"