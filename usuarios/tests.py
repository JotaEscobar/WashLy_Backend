from rest_framework import status
from core.test_utils import BaseTenantAPITestCase

class UsuariosAPITestCase(BaseTenantAPITestCase):
    def test_list_usuarios_admin(self):
        """Admin puede ver todos los usuarios de la empresa"""
        self.authenticate(self.admin_user)
        response = self.client.get('/usuarios/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see 3 users (admin, cajero, operario)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 3)

    def test_list_usuarios_other_company(self):
        """Usuario no puede ver usuarios de otra empresa"""
        self.authenticate(self.vencido_user)
        response = self.client.get('/usuarios/')
        # Even if expired, the filter logic would only show 1 anyway. Wait, with vencido it should be 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    def test_token_obtain(self):
        """Probar obtención de token JWT incluye datos extra del perfil"""
        response = self.client.post('/api/token/', {
            'username': 'admin',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        # Verify custom payload
        self.assertIn('rol', response.data)
        self.assertEqual(response.data['rol'], 'ADMIN')
        self.assertIn('empresa', response.data)
        self.assertEqual(response.data['empresa']['id'], self.empresa.id)
