"""
URLs principales de Washly
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

# Auth JWT
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from usuarios.views import CustomTokenObtainPairView, UsuarioViewSet

# ViewSets
from tickets.views import ClienteViewSet, TicketViewSet, TicketItemViewSet
from servicios.views import (
    CategoriaServicioViewSet, ServicioViewSet, TipoPrendaViewSet,
    PrendaViewSet, PromocionViewSet
)
from core.views import EmpresaViewSet, SedeViewSet
from pagos.views import MetodoPagoConfigViewSet

router = DefaultRouter()

# Core
router.register(r'core/empresa', EmpresaViewSet, basename='empresa')
router.register(r'core/sedes', SedeViewSet, basename='sede')

# Tickets y Clientes
router.register(r'clientes', ClienteViewSet, basename='cliente')
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'ticket-items', TicketItemViewSet, basename='ticketitem')

# Servicios
router.register(r'categorias-servicio', CategoriaServicioViewSet, basename='categoria-servicio')
router.register(r'servicios', ServicioViewSet, basename='servicio')
router.register(r'tipos-prenda', TipoPrendaViewSet, basename='tipo-prenda')
router.register(r'prendas', PrendaViewSet, basename='prenda')
router.register(r'promociones', PromocionViewSet, basename='promocion')

# Usuarios y Pagos
router.register(r'usuarios', UsuarioViewSet, basename='usuario')
router.register(r'pagos/config', MetodoPagoConfigViewSet, basename='metodopago')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- AUTHENTICATION (JWT) ---
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # --- API ROUTES (En raíz para coincidir con Frontend) ---
    path('', include(router.urls)),
    
    # Apps urls
    path('inventario/', include('inventario.urls')),
    path('pagos/', include('pagos.urls')),
    path('notificaciones/', include('notificaciones.urls')),
    path('reportes/', include('reportes.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)