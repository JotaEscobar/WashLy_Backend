"""
Constantes para el módulo de Tickets
"""

class TicketEstados:
    """Estados posibles de un ticket"""
    RECIBIDO = 'RECIBIDO'
    EN_PROCESO = 'EN_PROCESO'
    LISTO = 'LISTO'
    ENTREGADO = 'ENTREGADO'
    CANCELADO = 'CANCELADO'
    
    CHOICES = [
        (RECIBIDO, 'Recibido'),
        (EN_PROCESO, 'En Proceso'),
        (LISTO, 'Listo para Entrega'),
        (ENTREGADO, 'Entregado'),
        (CANCELADO, 'Cancelado'),
    ]
    
    @classmethod
    def get_label(cls, estado):
        """Retorna el label legible de un estado"""
        for choice, label in cls.CHOICES:
            if choice == estado:
                return label
        return estado


class TicketPrioridades:
    """Prioridades posibles de un ticket"""
    NORMAL = 'NORMAL'
    EXPRESS = 'EXPRESS'
    URGENTE = 'URGENTE'
    
    CHOICES = [
        (NORMAL, 'Normal'),
        (EXPRESS, 'Express'),
        (URGENTE, 'Urgente'),
    ]
