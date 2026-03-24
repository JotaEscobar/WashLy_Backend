from rest_framework import status
from core.test_utils import BaseTenantAPITestCase
from servicios.models import CategoriaServicio, Servicio, TipoPrenda, Prenda

class ServiciosAPITestCase(BaseTenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.categoria = CategoriaServicio.objects.create(
            empresa=self.empresa,
            nombre="Lavado de prendas"
        )
        self.servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre="Servicio Estandar",
            categoria=self.categoria,
            precio_base=15.00
        )
        self.tipo_prenda = TipoPrenda.objects.create(
            empresa=self.empresa,
            nombre="Abrigos"
        )
        self.prenda = Prenda.objects.create(
            empresa=self.empresa,
            nombre="Saco polar",
            tipo=self.tipo_prenda
        )
        
    def test_listar_categorias(self):
        """Asegurar que las categorías listadas de servicios son de la empresa del usuario"""
        self.authenticate(self.cajero_user)
        response = self.client.get('/categorias-servicio/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)

    def test_aislamiento_empresa_servicios(self):
        """Asegurar que no se escapan servicios entre tenants"""
        # User de la otra empresa (vencida)
        self.authenticate(self.vencido_user)
        response = self.client.get('/servicios/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_creacion_prenda(self):
        """Asegurar de que un administrador puede crear una prenda"""
        self.authenticate(self.admin_user)
        payload = {
            "nombre": "Casaca",
            "tipo": self.tipo_prenda.id,
        }
        response = self.client.post('/prendas/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['nombre'], "Casaca")
