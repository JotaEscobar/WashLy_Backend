# Corrección Aplicada: Desglose de Pagos

He solucionado el problema donde los montos de "Saldo Total" no coincidían con el "Desglose" (Efectivo/Yape/etc).

**Causa:**
Algunos pagos antiguos o modificados habían perdido su configuración de "Método de Pago" (ej: si se borró la configuración de Yape en el admin).

**Solución:**
He modificado `pagos/serializers.py` para que, si falta la configuración, el sistema busque el nombre histórico (`snapshot`) que se guardó al momento del pago (ej: "Yape de Juan"). Si encuentra "Yape", "Efectivo", etc., lo asigna correctamente al desglose en lugar de ocultarlo.

**Resultado:**
Ahora el "Saldo Total" y la suma del "Desglose" deben coincidir perfectamente en la Caja.
