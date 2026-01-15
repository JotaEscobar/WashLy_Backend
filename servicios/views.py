"""
Views para la app servicios
Actualizado para SaaS (Multi-tenant) manteniendo lógica de negocio completa
"""

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    CategoriaServicio, Servicio, TipoPrenda, Prenda,
    PrecioPorPrenda, Promocion
)
from .serializers import (
    CategoriaServicioSerializer, ServicioSerializer, ServicioListSerializer,
    TipoPrendaSerializer, PrendaSerializer, PrecioPorPrendaSerializer,
    PromocionSerializer, CalcularPrecioSerializer
)

class BaseTenantViewSet(viewsets.ModelViewSet):
    """
    Clase base para filtrar automáticamente por empresa y asignar auditoría.
    Evita repetir código en cada ViewSet.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Filtra siempre por la empresa del usuario logueado
        # Excluye registros marcados como eliminados (soft delete) si aplica
        return self.queryset.model.objects.filter(
            empresa=self.request.user.perfil.empresa, 
            activo=True
        )

    def perform_create(self, serializer):
        # Asigna automáticamente la empresa y el usuario creador
        serializer.save(
            empresa=self.request.user.perfil.empresa,
            creado_por=self.request.user
        )
    
    def perform_update(self, serializer):
        serializer.save(actualizado_por=self.request.user)


class CategoriaServicioViewSet(BaseTenantViewSet):
    queryset = CategoriaServicio.objects.all()
    serializer_class = CategoriaServicioSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['orden', 'nombre']
    ordering = ['orden', 'nombre']


class ServicioViewSet(BaseTenantViewSet):
    queryset = Servicio.objects.all().select_related('categoria')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'codigo', 'descripcion']
    ordering_fields = ['nombre', 'precio_base']
    ordering = ['categoria', 'nombre']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ServicioListSerializer
        return ServicioSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por categoría
        categoria_id = self.request.query_params.get('categoria', None)
        if categoria_id:
            queryset = queryset.filter(categoria_id=categoria_id)
        
        # Filtrar solo disponibles (para el POS)
        disponible = self.request.query_params.get('disponible', None)
        if disponible == 'true':
            queryset = queryset.filter(disponible=True)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def establecer_precio_prenda(self, request, pk=None):
        """Establece el precio para una prenda específica (SaaS Safe)"""
        servicio = self.get_object() # Ya filtra por tenant en get_queryset
        
        # Validar lógica de negocio
        if servicio.tipo_cobro != 'POR_PRENDA':
            return Response(
                {'error': 'Este servicio no cobra por prenda, edite el precio base.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Usamos update_or_create para evitar duplicados y asignar tenant
        precio_obj, created = PrecioPorPrenda.objects.update_or_create(
            servicio=servicio,
            prenda_id=request.data.get('prenda'),
            defaults={
                'precio': request.data.get('precio'),
                'empresa': request.user.perfil.empresa, # Vital para SaaS
                'creado_por': request.user
            }
        )
        
        serializer = PrecioPorPrendaSerializer(precio_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TipoPrendaViewSet(BaseTenantViewSet):
    queryset = TipoPrenda.objects.all()
    serializer_class = TipoPrendaSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre']
    ordering = ['nombre']


class PrendaViewSet(BaseTenantViewSet):
    queryset = Prenda.objects.all().select_related('tipo')
    serializer_class = PrendaSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre']
    ordering = ['tipo', 'nombre']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        tipo_id = self.request.query_params.get('tipo', None)
        if tipo_id:
            queryset = queryset.filter(tipo_id=tipo_id)
        return queryset


class PromocionViewSet(BaseTenantViewSet):
    queryset = Promocion.objects.all()
    serializer_class = PromocionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'codigo', 'descripcion']
    ordering = ['-fecha_inicio']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        validas = self.request.query_params.get('validas', None)
        if validas == 'true':
            hoy = timezone.now().date()
            queryset = queryset.filter(
                activa=True,
                fecha_inicio__lte=hoy,
                fecha_fin__gte=hoy
            )
        return queryset
    
    @action(detail=True, methods=['post'])
    def aplicar(self, request, pk=None):
        promocion = self.get_object()
        
        if not promocion.es_valida():
            return Response({'error': 'La promoción no es válida'}, status=status.HTTP_400_BAD_REQUEST)
        
        promocion.usos_actuales += 1
        promocion.save()
        
        return Response({
            'mensaje': 'Promoción aplicada',
            'usos_restantes': (promocion.usos_maximos - promocion.usos_actuales) if promocion.usos_maximos else None
        })
    
    @action(detail=False, methods=['post'])
    def calcular_precio(self, request):
        """Calcula el precio con promoción aplicada (SaaS Safe)"""
        serializer = CalcularPrecioSerializer(data=request.data)
        empresa_actual = request.user.perfil.empresa
        
        if serializer.is_valid():
            servicio_id = serializer.validated_data['servicio_id']
            # SAAS SECURITY: Usar get_object_or_404 con filtro de empresa
            servicio = get_object_or_404(Servicio, id=servicio_id, empresa=empresa_actual)
            
            cantidad = serializer.validated_data['cantidad']
            prenda_id = serializer.validated_data.get('prenda_id')
            
            # 1. Determinar Precio Unitario Base
            precio_unitario = servicio.precio_base
            
            if servicio.tipo_cobro == 'POR_PRENDA' and prenda_id:
                # Buscar precio específico seguro
                precio_especifico = servicio.precios_prendas.filter(
                    prenda_id=prenda_id, 
                    # No hace falta filtrar empresa aquí porque servicio ya está filtrado, 
                    # pero por doble seguridad lo mantenemos si el modelo lo tiene.
                ).first()
                if precio_especifico:
                    precio_unitario = precio_especifico.precio
            
            # 2. Calcular Subtotal
            subtotal = precio_unitario * cantidad
            descuento = 0
            
            # 3. Aplicar Promoción
            codigo_promocion = serializer.validated_data.get('promocion_codigo')
            if codigo_promocion:
                try:
                    # SAAS SECURITY: Solo buscar promociones de MI empresa
                    promocion = Promocion.objects.get(
                        codigo=codigo_promocion, 
                        empresa=empresa_actual,
                        activa=True
                    )
                    if promocion.es_valida():
                        descuento = promocion.calcular_descuento(subtotal)
                except Promocion.DoesNotExist:
                    pass # Código inválido o de otra empresa, lo ignoramos
            
            total = subtotal - descuento
            
            return Response({
                'precio_unitario': float(precio_unitario),
                'cantidad': float(cantidad),
                'subtotal': float(subtotal),
                'descuento': float(descuento),
                'total': float(total)
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)