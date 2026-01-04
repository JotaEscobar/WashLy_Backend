"""
Views para la app servicios
"""

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import (
    CategoriaServicio, Servicio, TipoPrenda, Prenda,
    PrecioPorPrenda, Promocion
)
from .serializers import (
    CategoriaServicioSerializer, ServicioSerializer, ServicioListSerializer,
    TipoPrendaSerializer, PrendaSerializer, PrecioPorPrendaSerializer,
    PromocionSerializer, CalcularPrecioSerializer
)


class CategoriaServicioViewSet(viewsets.ModelViewSet):
    queryset = CategoriaServicio.objects.filter(activo=True)
    serializer_class = CategoriaServicioSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['orden', 'nombre']
    ordering = ['orden', 'nombre']


class ServicioViewSet(viewsets.ModelViewSet):
    queryset = Servicio.objects.filter(activo=True).select_related('categoria')
    permission_classes = [IsAuthenticated]
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
        
        # Filtrar solo disponibles
        disponible = self.request.query_params.get('disponible', None)
        if disponible == 'true':
            queryset = queryset.filter(disponible=True)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def establecer_precio_prenda(self, request, pk=None):
        """Establece el precio para una prenda específica"""
        servicio = self.get_object()
        serializer = PrecioPorPrendaSerializer(data={
            'servicio': servicio.id,
            'prenda': request.data.get('prenda'),
            'precio': request.data.get('precio')
        })
        
        if serializer.is_valid():
            serializer.save(creado_por=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TipoPrendaViewSet(viewsets.ModelViewSet):
    queryset = TipoPrenda.objects.filter(activo=True)
    serializer_class = TipoPrendaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre']
    ordering = ['nombre']


class PrendaViewSet(viewsets.ModelViewSet):
    queryset = Prenda.objects.filter(activo=True).select_related('tipo')
    serializer_class = PrendaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre']
    ordering = ['tipo', 'nombre']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por tipo
        tipo_id = self.request.query_params.get('tipo', None)
        if tipo_id:
            queryset = queryset.filter(tipo_id=tipo_id)
        
        return queryset


class PromocionViewSet(viewsets.ModelViewSet):
    queryset = Promocion.objects.filter(activo=True)
    serializer_class = PromocionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'codigo', 'descripcion']
    ordering = ['-fecha_inicio']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar solo promociones activas y válidas
        validas = self.request.query_params.get('validas', None)
        if validas == 'true':
            from django.utils import timezone
            hoy = timezone.now().date()
            queryset = queryset.filter(
                activa=True,
                fecha_inicio__lte=hoy,
                fecha_fin__gte=hoy
            )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def aplicar(self, request, pk=None):
        """Aplica una promoción y aumenta el contador de usos"""
        promocion = self.get_object()
        
        if not promocion.es_valida():
            return Response(
                {'error': 'La promoción no es válida'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        promocion.usos_actuales += 1
        promocion.save()
        
        return Response({
            'mensaje': 'Promoción aplicada',
            'usos_restantes': (promocion.usos_maximos - promocion.usos_actuales) if promocion.usos_maximos else None
        })
    
    @action(detail=False, methods=['post'])
    def calcular_precio(self, request):
        """Calcula el precio con promoción aplicada"""
        serializer = CalcularPrecioSerializer(data=request.data)
        
        if serializer.is_valid():
            servicio = Servicio.objects.get(id=serializer.validated_data['servicio_id'])
            cantidad = serializer.validated_data['cantidad']
            prenda_id = serializer.validated_data.get('prenda_id')
            
            # Obtener precio base
            precio_unitario = servicio.precio_base
            if prenda_id:
                precio_especifico = servicio.precios_prendas.filter(prenda_id=prenda_id).first()
                if precio_especifico:
                    precio_unitario = precio_especifico.precio
            
            subtotal = precio_unitario * cantidad
            descuento = 0
            
            # Aplicar promoción si existe
            codigo_promocion = serializer.validated_data.get('promocion_codigo')
            if codigo_promocion:
                try:
                    promocion = Promocion.objects.get(codigo=codigo_promocion, activo=True)
                    if promocion.es_valida():
                        descuento = promocion.calcular_descuento(subtotal)
                except Promocion.DoesNotExist:
                    pass
            
            total = subtotal - descuento
            
            return Response({
                'precio_unitario': float(precio_unitario),
                'cantidad': cantidad,
                'subtotal': float(subtotal),
                'descuento': float(descuento),
                'total': float(total)
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
