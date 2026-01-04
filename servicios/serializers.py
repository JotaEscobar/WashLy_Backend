"""
Serializers para la app servicios
"""

from rest_framework import serializers
from .models import (
    CategoriaServicio, Servicio, TipoPrenda, Prenda,
    PrecioPorPrenda, Promocion
)


class CategoriaServicioSerializer(serializers.ModelSerializer):
    cantidad_servicios = serializers.SerializerMethodField()
    
    class Meta:
        model = CategoriaServicio
        fields = [
            'id', 'nombre', 'descripcion', 'icono', 'orden',
            'activo', 'cantidad_servicios', 'creado_en'
        ]
        read_only_fields = ['creado_en']
    
    def get_cantidad_servicios(self, obj):
        return obj.servicios.filter(activo=True, disponible=True).count()


class TipoPrendaSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoPrenda
        fields = ['id', 'nombre', 'descripcion', 'icono', 'activo', 'creado_en']
        read_only_fields = ['creado_en']


class PrendaSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source='tipo.nombre', read_only=True)
    
    class Meta:
        model = Prenda
        fields = [
            'id', 'nombre', 'tipo', 'tipo_nombre',
            'multiplicador_precio', 'activo', 'creado_en'
        ]
        read_only_fields = ['creado_en']


class PrecioPorPrendaSerializer(serializers.ModelSerializer):
    servicio_nombre = serializers.CharField(source='servicio.nombre', read_only=True)
    prenda_nombre = serializers.CharField(source='prenda.nombre', read_only=True)
    
    class Meta:
        model = PrecioPorPrenda
        fields = [
            'id', 'servicio', 'servicio_nombre', 'prenda',
            'prenda_nombre', 'precio', 'creado_en'
        ]
        read_only_fields = ['creado_en']


class ServicioSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    precios_prendas = PrecioPorPrendaSerializer(many=True, read_only=True)
    sedes_nombres = serializers.SerializerMethodField()
    
    class Meta:
        model = Servicio
        fields = [
            'id', 'nombre', 'codigo', 'descripcion', 'categoria',
            'categoria_nombre', 'precio_base', 'tiempo_estimado',
            'requiere_prenda', 'disponible', 'sedes', 'sedes_nombres',
            'precios_prendas', 'activo', 'creado_en'
        ]
        read_only_fields = ['creado_en']
    
    def get_sedes_nombres(self, obj):
        return [sede.nombre for sede in obj.sedes.all()]


class ServicioListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados"""
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    
    class Meta:
        model = Servicio
        fields = [
            'id', 'nombre', 'codigo', 'categoria_nombre',
            'precio_base', 'disponible'
        ]


class PromocionSerializer(serializers.ModelSerializer):
    servicios_nombres = serializers.SerializerMethodField()
    es_valida = serializers.ReadOnlyField()
    
    class Meta:
        model = Promocion
        fields = [
            'id', 'nombre', 'codigo', 'descripcion', 'tipo',
            'valor_descuento', 'servicios', 'servicios_nombres',
            'fecha_inicio', 'fecha_fin', 'monto_minimo', 'cantidad_minima',
            'activa', 'usos_maximos', 'usos_actuales', 'es_valida',
            'activo', 'creado_en'
        ]
        read_only_fields = ['creado_en', 'usos_actuales', 'es_valida']
    
    def get_servicios_nombres(self, obj):
        return [servicio.nombre for servicio in obj.servicios.all()]


class CalcularPrecioSerializer(serializers.Serializer):
    """Serializer para calcular precios"""
    servicio_id = serializers.IntegerField()
    prenda_id = serializers.IntegerField(required=False, allow_null=True)
    cantidad = serializers.IntegerField(default=1, min_value=1)
    promocion_codigo = serializers.CharField(required=False, allow_blank=True)
