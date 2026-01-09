from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PagoViewSet, CajaViewSet

router = DefaultRouter()
router.register(r'', PagoViewSet, basename='pago') 
router.register(r'caja', CajaViewSet, basename='caja')  

urlpatterns = [
    path('', include(router.urls)),
]