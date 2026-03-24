from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Producto, MovimientoInventario

class InventarioService:
    @staticmethod
    def registrar_movimiento(producto, tipo, cantidad, empresa, user, motivo='', costo=None):
        """Lógica centralizada para movimientos de stock"""
        with transaction.atomic():
            stock_anterior = producto.stock_actual
            
            if tipo == 'COMPRA':
                producto.stock_actual += cantidad
                if costo:
                    producto.precio_compra = costo
            elif tipo == 'CONSUMO':
                if producto.stock_actual < cantidad:
                    raise ValidationError(f"Stock insuficiente: {producto.stock_actual}")
                producto.stock_actual -= cantidad
            elif tipo == 'AJUSTE':
                producto.stock_actual = cantidad
            
            stock_nuevo = producto.stock_actual
            producto.save()

            movimiento = MovimientoInventario.objects.create(
                producto=producto,
                tipo=tipo,
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_nuevo=stock_nuevo,
                empresa=empresa,
                creado_por=user,
                motivo=motivo,
                costo_unitario=costo
            )
            return movimiento

    @staticmethod
    def get_kardex(producto):
        return producto.movimientos.all().order_by('-creado_en')
