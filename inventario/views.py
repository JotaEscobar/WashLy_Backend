from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import CategoriaProducto, Producto, MovimientoInventario
from .serializers import (
    CategoriaProductoSerializer, ProductoSerializer,
    MovimientoInventarioSerializer
)

class CategoriaProductoViewSet(viewsets.ModelViewSet):
    queryset = CategoriaProducto.objects.filter(activo=True)
    serializer_class = CategoriaProductoSerializer

class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.filter(activo=True)
    serializer_class = ProductoSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'codigo']
    ordering_fields = ['stock_actual', 'nombre']

    @action(detail=True, methods=['get'])
    def kardex(self, request, pk=None):
        # Historial específico de un producto
        producto = self.get_object()
        movimientos = producto.movimientos.all().order_by('-creado_en')
        serializer = MovimientoInventarioSerializer(movimientos, many=True)
        return Response(serializer.data)

class MovimientoInventarioViewSet(viewsets.ModelViewSet):
    queryset = MovimientoInventario.objects.all()
    serializer_class = MovimientoInventarioSerializer
    
    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)