from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Servicio, Prenda, TipoPrenda, PrecioPorPrenda, Promocion

class ServicioService:
    @staticmethod
    def establecer_precio_prenda(servicio, empresa, user, data):
        """Lógica de Upsert de precio por prenda con creación al vuelo"""
        if servicio.tipo_cobro != 'POR_PRENDA':
            return None, "Este servicio no cobra por prenda"

        prenda_id = data.get('prenda') or data.get('prenda_id')
        nombre_prenda = data.get('nombre_prenda')
        precio = data.get('precio')

        if not precio:
            return None, "El precio es obligatorio"

        try:
            with transaction.atomic():
                prenda = None
                if prenda_id:
                    prenda = get_object_or_404(Prenda, id=prenda_id, empresa=empresa)
                elif nombre_prenda:
                    nombre_clean = nombre_prenda.strip()
                    prenda = Prenda.objects.filter(empresa=empresa, nombre__iexact=nombre_clean).first()

                    if not prenda:
                        tipo_id = data.get('tipo_prenda_id')
                        if tipo_id:
                            tipo = get_object_or_404(TipoPrenda, id=tipo_id, empresa=empresa)
                        else:
                            tipo, _ = TipoPrenda.objects.get_or_create(
                                nombre="General", 
                                empresa=empresa, 
                                defaults={'creado_por': user}
                            )
                        prenda = Prenda.objects.create(
                            nombre=nombre_clean,
                            tipo=tipo,
                            empresa=empresa,
                            creado_por=user
                        )
                else:
                    return None, "Debe seleccionar una prenda o ingresar un nombre"

                precio_obj, _ = PrecioPorPrenda.objects.update_or_create(
                    servicio=servicio,
                    prenda=prenda,
                    defaults={'precio': precio, 'empresa': empresa, 'creado_por': user}
                )
                return precio_obj, "Precio establecido"
        except Exception as e:
            return None, str(e)

class PromocionService:
    @staticmethod
    def calcular_cotizacion(empresa, data):
        """Calcula el desglose de precio, subtotal y descuentos"""
        servicio_id = data['servicio_id']
        servicio = get_object_or_404(Servicio, id=servicio_id, empresa=empresa)
        
        cantidad = data['cantidad']
        prenda_id = data.get('prenda_id')
        
        # 1. Precio Base
        precio_unitario = servicio.precio_base
        if servicio.tipo_cobro == 'POR_PRENDA' and prenda_id:
            precio_especifico = servicio.precios_prendas.filter(prenda_id=prenda_id).first()
            if precio_especifico:
                precio_unitario = precio_especifico.precio
        
        # 2. Subtotal
        subtotal = precio_unitario * cantidad
        descuento = 0
        
        # 3. Descuento Promocional
        codigo_promocion = data.get('promocion_codigo')
        if codigo_promocion:
            try:
                promocion = Promocion.objects.get(codigo=codigo_promocion, empresa=empresa, activa=True)
                if promocion.es_valida():
                    descuento = promocion.calcular_descuento(subtotal)
            except Promocion.DoesNotExist:
                pass
        
        return {
            'precio_unitario': float(precio_unitario),
            'cantidad': float(cantidad),
            'subtotal': float(subtotal),
            'descuento': float(descuento),
            'total': float(subtotal - descuento)
        }
