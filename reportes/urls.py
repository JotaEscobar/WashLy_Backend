from django.urls import path
from .views import (
    DashboardKPIView,
    DashboardOperativoView,
    DashboardAnaliticaView,
    ReportePDFView
)
urlpatterns = [
    # Dashboards de Tenant (Lavandería)
    path('dashboard/kpis/', DashboardKPIView.as_view(), name='dashboard-kpis'),
    path('dashboard/operativo/', DashboardOperativoView.as_view(), name='dashboard-operativo'),
    path('dashboard/analitica/', DashboardAnaliticaView.as_view(), name='dashboard-analitica'),
    path('exportar/pdf/', ReportePDFView.as_view(), name='reporte-pdf'),


]
