from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PagoViewSet

router = DefaultRouter()
router.register(r'', PagoViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
