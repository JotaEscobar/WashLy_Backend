from rest_framework import serializers
from .models import CategoriaProducto, Producto, MovimientoInventario, AlertaStock

class CategoriaProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaProducto
        fields = ['id', 'nombre']

class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    valor_inventario = serializers.SerializerMethodField()
    estado = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            'id', 'codigo', 'nombre', 'descripcion', 
            'categoria', 'categoria_nombre',
            'unidad_medida', 'stock_actual', 'stock_minimo', 
            'precio_compra', 'valor_inventario', 'estado'
        ]
    
    def get_valor_inventario(self, obj):
        # Valor monetario aproximado del stock actual
        precio = obj.precio_compra or 0
        return float(obj.stock_actual * precio)

    def get_estado(self, obj):
        if obj.stock_actual <= 0: return 'AGOTADO'
        if obj.stock_actual <= obj.stock_minimo: return 'BAJO'
        return 'OK'

class MovimientoInventarioSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    usuario = serializers.CharField(source='creado_por.username', read_only=True)
    
    class Meta:
        model = MovimientoInventario
        fields = [
            'id', 'producto', 'producto_nombre', 'tipo', 
            'cantidad', 'stock_anterior', 'stock_nuevo', 
            'motivo', 'costo_unitario', 'creado_en', 'usuario'
        ]
        read_only_fields = ['stock_anterior', 'stock_nuevo', 'creado_en']

    def validate(self, data):
        """Validación para asegurar que hay stock suficiente antes de guardar"""
        if data.get('tipo') == 'CONSUMO':
            producto = data.get('producto')
            cantidad = data.get('cantidad')
            if producto and cantidad and producto.stock_actual < cantidad:
                raise serializers.ValidationError({
                    "cantidad": f"Stock insuficiente. Disponible: {producto.stock_actual} {producto.unidad_medida}"
                })
        return data

class AlertaStockSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model = AlertaStock
        fields = ['id', 'producto', 'producto_nombre', 'mensaje', 'fecha']