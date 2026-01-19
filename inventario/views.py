from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import CategoriaProducto, Producto, MovimientoInventario, AlertaStock
from .serializers import (
    CategoriaProductoSerializer, ProductoSerializer,
    MovimientoInventarioSerializer, AlertaStockSerializer
)
from core.permissions import IsActiveSubscription

class BaseTenantViewSet(viewsets.ModelViewSet):
    """
    Clase base para asegurar filtrado por empresa en Inventario.
    Evita fuga de datos entre inquilinos.
    """
    permission_classes = [permissions.IsAuthenticated, IsActiveSubscription]

    def get_queryset(self):
        # Filtra siempre por la empresa del usuario logueado
        return self.queryset.model.objects.filter(
            empresa=self.request.user.perfil.empresa,
            activo=True
        )

    def perform_create(self, serializer):
        serializer.save(
            empresa=self.request.user.perfil.empresa
        )

class CategoriaProductoViewSet(BaseTenantViewSet):
    queryset = CategoriaProducto.objects.all()
    serializer_class = CategoriaProductoSerializer

class ProductoViewSet(BaseTenantViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'codigo']
    ordering_fields = ['stock_actual', 'nombre']

    @action(detail=True, methods=['get'])
    def kardex(self, request, pk=None):
        producto = self.get_object() # Ya filtra por empresa gracias a BaseTenantViewSet
        movimientos = producto.movimientos.all().order_by('-creado_en')
        serializer = MovimientoInventarioSerializer(movimientos, many=True)
        return Response(serializer.data)

class MovimientoInventarioViewSet(BaseTenantViewSet):
    queryset = MovimientoInventario.objects.all()
    serializer_class = MovimientoInventarioSerializer
    
    def perform_create(self, serializer):
        # Sobreescribimos para añadir el usuario creador además de la empresa
        serializer.save(
            empresa=self.request.user.perfil.empresa,
            creado_por=self.request.user
        )

class AlertaStockViewSet(BaseTenantViewSet):
    queryset = AlertaStock.objects.all().order_by('-fecha')
    serializer_class = AlertaStockSerializer