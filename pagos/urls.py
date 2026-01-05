from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PagoViewSet, CajaViewSet

router = DefaultRouter()
router.register(r'lista', PagoViewSet) # /api/pagos/lista/
router.register(r'caja', CajaViewSet)  # /api/pagos/caja/

urlpatterns = [
    path('', include(router.urls)),
]