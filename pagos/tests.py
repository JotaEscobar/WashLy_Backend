from rest_framework import status
from django.utils import timezone
from core.test_utils import BaseTenantAPITestCase
from pagos.models import MetodoPagoConfig, CajaSesion, Pago
from tickets.models import Cliente, Ticket

class PagosAPITestCase(BaseTenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.metodo = MetodoPagoConfig.objects.create(
            empresa=self.empresa,
            codigo_metodo="EFECTIVO",
            nombre_mostrar="Efectivo en Caja"
        )
        
        # Necesitamos un ticket activo
        self.cliente = Cliente.objects.create(
            empresa=self.empresa,
            numero_documento="77777777",
            nombres="Bob"
        )
        self.ticket = Ticket.objects.create(
            empresa=self.empresa,
            sede=self.sede_principal,
            cliente=self.cliente,
            fecha_prometida=timezone.now()
        )

    def test_abrir_caja(self):
        """Asegurar que un cajero puede abrir caja y se asocia a su sede"""
        self.authenticate(self.cajero_user)
        response = self.client.post('/pagos/caja/abrir/', {
            "monto_inicial": 100.00
        })
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        caja = CajaSesion.objects.get(id=response.data['id'])
        self.assertEqual(caja.usuario, self.cajero_user)
        self.assertEqual(caja.sede, self.sede_principal)
        self.assertEqual(caja.estado, 'ABIERTA')

    def test_evitar_doble_caja(self):
        """Un usuario no debe poder tener dos cajas abiertas en la misma sede"""
        CajaSesion.objects.create(
            empresa=self.empresa,
            usuario=self.cajero_user,
            sede=self.sede_principal,
            estado='ABIERTA',
            monto_inicial=50.00
        )
        self.authenticate(self.cajero_user)
        response = self.client.post('/pagos/caja/abrir/', {
            "monto_inicial": 100.00
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_realizar_pago_vincula_caja(self):
        """Al crear un pago, debe vincularse automáticamente a una caja abierta"""
        # Abrimos caja primero manualmente para el usuario que hará la prueba (creado_por se usará en pago.save())
        caja = CajaSesion.objects.create(
            empresa=self.empresa,
            usuario=self.admin_user,
            sede=self.sede_principal,
            estado='ABIERTA',
            monto_inicial=0
        )
        
        self.authenticate(self.admin_user)
        response = self.client.post('/pagos/', {
            "ticket": self.ticket.id,
            "metodo_pago_config": self.metodo.id,
            "monto": 50.00,
            "referencia": "Recibo 001"
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verificar pago y asociación con caja
        pago = Pago.objects.get(id=response.data['id'])
        self.assertEqual(pago.caja, caja)
        self.assertEqual(pago.ticket, self.ticket)

    def test_aislamiento_tenant_metodos_pago(self):
        self.authenticate(self.vencido_user)
        response = self.client.get('/pagos/config/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 0)
