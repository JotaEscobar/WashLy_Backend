from rest_framework import status
from core.test_utils import BaseTenantAPITestCase
from inventario.models import CategoriaProducto, Producto, MovimientoInventario

class InventarioAPITestCase(BaseTenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.categoria = CategoriaProducto.objects.create(
            empresa=self.empresa,
            nombre="Detergentes"
        )
        self.producto = Producto.objects.create(
            empresa=self.empresa,
            sede=self.sede_principal,
            nombre="Jabon Liquido",
            codigo="JL-01",
            categoria=self.categoria,
            unidad_medida="L",
            stock_actual=10.0,
            stock_minimo=5.0
        )

    def test_producto_stock_bajo(self):
        """Probar propiedad stock_bajo = False si es mayor al mínimo"""
        self.assertFalse(self.producto.stock_bajo)
        
        self.producto.stock_actual = 5.0
        self.producto.save()
        self.assertTrue(self.producto.stock_bajo)

    def test_movimiento_inventario_consumo(self):
        """Asegurar que un movimiento de tipo CONSUMO reduce el stock_actual y genera validaciones"""
        MovimientoInventario.objects.create(
            empresa=self.empresa,
            producto=self.producto,
            tipo='CONSUMO',
            cantidad=3.0,
            stock_anterior=10.0,
            stock_nuevo=7.0
        )
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 7.0)

    def test_movimiento_inventario_compra(self):
        """Asegurar que un movimiento de COMPRA aumenta stock y modifica precio ref"""
        MovimientoInventario.objects.create(
            empresa=self.empresa,
            producto=self.producto,
            tipo='COMPRA',
            cantidad=5.0,
            costo_unitario=2.50,
            stock_anterior=10.0,
            stock_nuevo=15.0
        )
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 15.0)
        self.assertEqual(self.producto.precio_compra, 2.50)

    def test_api_list_productos_sede(self):
        """Un usuario debe ver los productos que pertenecen a su sede"""
        self.authenticate(self.cajero_user)
        response = self.client.get('/inventario/productos/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)

    def test_api_list_ventanilla(self):
        """Aislar productos por sede, admin lo ve si no hay filtro explícito"""
        self.authenticate(self.vencido_user)
        response = self.client.get('/inventario/productos/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
