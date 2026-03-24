"""
Views para la app servicios
Actualizado para SaaS (Multi-tenant) con Lógica de Precios Dinámica (Upsert)
"""

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from core.permissions import IsActiveSubscription  # ✅ AGREGADO
from core.mixins import resolver_sede_desde_request
from .services import ServicioService, PromocionService

from .models import (
    CategoriaServicio, Servicio, TipoPrenda, Prenda,
    PrecioPorPrenda, Promocion
)
from .serializers import (
    CategoriaServicioSerializer, ServicioSerializer, ServicioListSerializer,
    TipoPrendaSerializer, PrendaSerializer, PrecioPorPrendaSerializer,
    PromocionSerializer, CalcularPrecioSerializer
)

from core.views import BaseTenantViewSet

class CategoriaServicioViewSet(BaseTenantViewSet):
    queryset = CategoriaServicio.objects.all()
    serializer_class = CategoriaServicioSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['orden', 'nombre']
    ordering = ['orden', 'nombre']


class ServicioViewSet(BaseTenantViewSet):
    queryset = Servicio.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'codigo', 'descripcion']
    ordering_fields = ['nombre', 'precio_base']
    ordering = ['categoria', 'nombre']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ServicioListSerializer
        return ServicioSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('categoria')
        
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
        """Usa ServicioService para la lógica de upsert y creación al vuelo"""
        servicio = self.get_object() 
        empresa = request.user.perfil.empresa
        user = request.user
        
        # Delegamos al servicio
        precio_obj, mensaje = ServicioService.establecer_precio_prenda(servicio, empresa, user, request.data)
        
        if not precio_obj:
            return Response({'error': mensaje}, status=status.HTTP_400_BAD_REQUEST if "precio" in mensaje else 500)
        
        serializer = PrecioPorPrendaSerializer(precio_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'])
    def eliminar_precio_prenda(self, request, pk=None):
        """Elimina la asociación de precio de una prenda con este servicio"""
        servicio = self.get_object()
        prenda_id = request.data.get('prenda_id')
        
        deleted, _ = PrecioPorPrenda.objects.filter(
            servicio=servicio,
            prenda_id=prenda_id,
            empresa=request.user.perfil.empresa
        ).delete()
        
        if deleted:
            return Response({'status': 'Precio eliminado correctamente'})
        return Response({'error': 'No se encontró el precio especificado'}, status=404)


class TipoPrendaViewSet(BaseTenantViewSet):
    queryset = TipoPrenda.objects.all()
    serializer_class = TipoPrendaSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre']
    ordering = ['nombre']


class PrendaViewSet(BaseTenantViewSet):
    queryset = Prenda.objects.all()
    serializer_class = PrendaSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre']
    ordering = ['tipo', 'nombre']
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('tipo')
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
        """Calcula el precio con promoción aplicada usando PromocionService (DRY)"""
        serializer = CalcularPrecioSerializer(data=request.data)
        if serializer.is_valid():
            empresa = request.user.perfil.empresa
            resumen = PromocionService.calcular_cotizacion(empresa, serializer.validated_data)
            return Response(resumen)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)