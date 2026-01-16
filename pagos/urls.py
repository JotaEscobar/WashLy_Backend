from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PagoViewSet, CajaViewSet, MetodoPagoConfigViewSet

router = DefaultRouter()
router.register(r'config', MetodoPagoConfigViewSet, basename='metodopago')
router.register(r'caja', CajaViewSet, basename='caja')  
router.register(r'', PagoViewSet, basename='pago') 

urlpatterns = [
    path('', include(router.urls)),
]