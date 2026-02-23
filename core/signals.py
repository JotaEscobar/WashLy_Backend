from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import HistorialSuscripcion, Empresa

@receiver(post_save, sender=HistorialSuscripcion)
def actualizar_vencimiento_empresa(sender, instance, created, **kwargs):
    """
    Cuando se registra un pago en el historial, actualiza automáticamente
    la fecha de vencimiento de la empresa asociada.
    """
    empresa = instance.empresa
    
    # Solo actualizamos si la fecha de fin del periodo es mayor a la actual de la empresa
    # o si se acaba de crear el registro de pago.
    if instance.periodo_fin:
        # Convertir Date a DateTime para comparar si es necesario
        from datetime import datetime
        fecha_fin_dt = timezone.make_aware(datetime.combine(instance.periodo_fin, datetime.min.time()))
        
        if not empresa.fecha_vencimiento or fecha_fin_dt > empresa.fecha_vencimiento:
            empresa.fecha_vencimiento = fecha_fin_dt
            # Si el plan era DEMO y está pagando, lo pasamos a MENSUAL
            if empresa.plan == 'DEMO':
                empresa.plan = 'MENSUAL'
            
            # Aseguramos que el estado sea ACTIVO
            empresa.estado = 'ACTIVO'
            empresa.save()
