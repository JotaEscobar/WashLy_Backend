from django.urls import path
from .views import DashboardView, ReporteVentasView

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('ventas/', ReporteVentasView.as_view(), name='reporte-ventas'),
]
