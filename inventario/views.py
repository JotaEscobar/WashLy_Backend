from rest_framework import viewsets, filters
from .models import CategoriaProducto, Producto, MovimientoInventario, AlertaStock
from .serializers import (
    CategoriaProductoSerializer, ProductoSerializer,
    MovimientoInventarioSerializer, AlertaStockSerializer
)

class CategoriaProductoViewSet(viewsets.ModelViewSet):
    queryset = CategoriaProducto.objects.filter(activo=True)
    serializer_class = CategoriaProductoSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['nombre']

class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.filter(activo=True)
    serializer_class = ProductoSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'codigo']
    ordering_fields = ['stock_actual']

class MovimientoInventarioViewSet(viewsets.ModelViewSet):
    queryset = MovimientoInventario.objects.all()
    serializer_class = MovimientoInventarioSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['-creado_en']

class AlertaStockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AlertaStock.objects.filter(resuelta=False)
    serializer_class = AlertaStockSerializer
    ordering = ['-fecha_alerta']
