from rest_framework import serializers
from pagos.models import CajaSesion, Pago, MetodoPagoConfig

def registrar_pago(user, empresa, ticket, monto, metodo_pago_id=None, metodo_pago_str=None, referencia=None):
    """
    Servicio centralizado para registrar pagos, asegurando que se validen contra la caja
    abierta del usuario y se asigne el método de pago correcto.
    """
    if float(monto) <= 0:
        return None

    # Validar Caja Abierta
    caja_abierta = CajaSesion.objects.filter(
        usuario=user, 
        empresa=empresa, 
        estado='ABIERTA'
    ).first()
    
    if not caja_abierta:
        raise serializers.ValidationError({
            "error": "No tienes una caja abierta. Apertura caja para recibir pagos."
        })
    
    # Resolver Configuración del Método de Pago
    metodo_config = None
    if metodo_pago_id:
        metodo_config = MetodoPagoConfig.objects.filter(id=metodo_pago_id, empresa=empresa).first()
    elif metodo_pago_str:
        # Intento de fallback inteligente: buscar por código
        metodo_config = MetodoPagoConfig.objects.filter(
            codigo_metodo=metodo_pago_str.upper(), 
            empresa=empresa
        ).first()

    snapshot = metodo_config.nombre_mostrar if metodo_config else (metodo_pago_str or "EFECTIVO")
    if not referencia:
        referencia = f'Pago Ticket {ticket.numero_ticket}'

    # Registrar el Pago
    pago = Pago.objects.create(
        ticket=ticket,
        caja=caja_abierta,
        monto=monto,
        metodo_pago_config=metodo_config,
        metodo_pago_snapshot=snapshot,
        estado='PAGADO',
        referencia=referencia,
        empresa=empresa,
        creado_por=user
    )
    
    return pago
