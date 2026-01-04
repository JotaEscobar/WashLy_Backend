from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoriaProductoViewSet, ProductoViewSet,
    MovimientoInventarioViewSet, AlertaStockViewSet
)

router = DefaultRouter()
router.register(r'categorias', CategoriaProductoViewSet)
router.register(r'productos', ProductoViewSet)
router.register(r'movimientos', MovimientoInventarioViewSet)
router.register(r'alertas', AlertaStockViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
