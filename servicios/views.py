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
        # Verifica si el modelo tiene el campo 'actualizado_por' antes de guardarlo
        if hasattr(serializer.instance, 'actualizado_por'):
            serializer.save(actualizado_por=self.request.user)
        else:
            serializer.save()


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
        """
        Establece el precio para una prenda específica.
        Soporta creación de prenda al vuelo si se envía 'nombre_prenda'.
        """
        servicio = self.get_object() # Ya filtra por tenant
        empresa = request.user.perfil.empresa
        user = request.user
        
        # 1. Validaciones
        if servicio.tipo_cobro != 'POR_PRENDA':
            return Response(
                {'error': 'Este servicio no cobra por prenda, edite el precio base.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        prenda_id = request.data.get('prenda') or request.data.get('prenda_id')
        nombre_prenda = request.data.get('nombre_prenda') # Nuevo campo para creación al vuelo
        precio = request.data.get('precio')

        if not precio:
            return Response({'error': 'El precio es obligatorio'}, status=400)

        # 2. Lógica de Obtención/Creación de Prenda
        prenda = None

        try:
            with transaction.atomic():
                if prenda_id:
                    # Caso A: Prenda existente seleccionada
                    prenda = get_object_or_404(Prenda, id=prenda_id, empresa=empresa)
                
                elif nombre_prenda:
                    # Caso B: Crear prenda nueva al vuelo
                    # Normalizamos el nombre para evitar duplicados por mayúsculas/minúsculas
                    nombre_clean = nombre_prenda.strip()
                    
                    # Buscamos si ya existe por nombre (case insensitive)
                    prenda = Prenda.objects.filter(
                        empresa=empresa, 
                        nombre__iexact=nombre_clean
                    ).first()

                    if not prenda:
                        # Si no existe, la creamos. 
                        # Necesitamos un TipoPrenda por defecto o enviado desde el front.
                        tipo_id = request.data.get('tipo_prenda_id')
                        tipo = None
                        
                        if tipo_id:
                            tipo = get_object_or_404(TipoPrenda, id=tipo_id, empresa=empresa)
                        else:
                            # Fallback: Buscar o crear un tipo "General" o "Varios"
                            tipo, _ = TipoPrenda.objects.get_or_create(
                                nombre="General", 
                                empresa=empresa, 
                                defaults={'creado_por': user, 'descripcion': 'Categoría automática'}
                            )
                        
                        prenda = Prenda.objects.create(
                            nombre=nombre_clean, # Guardamos el nombre limpio
                            tipo=tipo,
                            empresa=empresa,
                            creado_por=user,
                            activo=True
                        )

                else:
                    return Response({'error': 'Debe seleccionar una prenda o ingresar un nombre nuevo'}, status=400)

                # 3. Guardar el Precio (Upsert)
                precio_obj, created = PrecioPorPrenda.objects.update_or_create(
                    servicio=servicio,
                    prenda=prenda,
                    defaults={
                        'precio': precio,
                        'empresa': empresa, # Aseguramos tenant
                        'creado_por': user
                    }
                )

                # Si ya existía y tenía soft-delete (si aplicara), lo reactivamos (opcional según tu modelo)
                # En este caso PrecioPorPrenda es físico, así que update_or_create basta.

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
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
                    prenda_id=prenda_id
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