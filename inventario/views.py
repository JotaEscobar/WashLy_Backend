from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import CategoriaProducto, Producto, MovimientoInventario
from .serializers import (
    CategoriaProductoSerializer, ProductoSerializer,
    MovimientoInventarioSerializer
)
from core.permissions import IsActiveSubscription

from core.views import BaseTenantViewSet

from .services import InventarioService

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
        producto = self.get_object() 
        movimientos = InventarioService.get_kardex(producto)
        serializer = MovimientoInventarioSerializer(movimientos, many=True)
        return Response(serializer.data)

class MovimientoInventarioViewSet(BaseTenantViewSet):
    queryset = MovimientoInventario.objects.all()
    serializer_class = MovimientoInventarioSerializer
    
    def perform_create(self, serializer):
        # Delegamos el guardado complejo al servicio (opcionalmente)
        # O simplemente mantenemos el serializer.save si la lógica está en el modelo
        # Pero según Fase 3, la lógica debe estar en el servicio.
        # Así que idealmente llamamos al servicio aquí y luego el serializer solo refleja el dato.
        
        # Para que el serializer funcione bien con el servicio, vamos a capturar los datos
        # y usar el servicio para la transacción real.
        
        empresa = self.request.user.perfil.empresa
        user = self.request.user
        producto = serializer.validated_data['producto']
        tipo = serializer.validated_data['tipo']
        cantidad = serializer.validated_data['cantidad']
        motivo = serializer.validated_data.get('motivo', '')
        costo = serializer.validated_data.get('costo_unitario')

        mov = InventarioService.registrar_movimiento(
            producto=producto,
            tipo=tipo,
            cantidad=cantidad,
            empresa=empresa,
            user=user,
            motivo=motivo,
            costo=costo
        )
        # Sincronizamos el serializer con el objeto creado (si se necesita su data en el response)
        serializer.instance = mov
