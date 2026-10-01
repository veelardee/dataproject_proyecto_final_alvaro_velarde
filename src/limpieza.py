"""
Funciones de limpieza y preparación de los datos de Olist.

Cada función resuelve un problema concreto detectado en la auditoría inicial.
Están aquí y no en el notebook para poder reutilizarlas y corregirlas en un
único sitio.
"""

import numpy as np
import pandas as pd


# Límites aproximados del territorio brasileño. Se usan para descartar
# coordenadas imposibles en la tabla de geolocalización.
BRASIL_LAT = (-34.0, 5.3)
BRASIL_LNG = (-74.0, -34.0)

RADIO_TIERRA_KM = 6371.0


def consolidar_geolocalizacion(geo):
    """
    Reduce el millón de filas de geolocalización a una coordenada por código postal.

    La tabla original trae una fila por cada dirección registrada, así que un
    mismo código postal aparece cientos de veces con coordenadas ligeramente
    distintas. Unirla tal cual multiplicaría las filas de la tabla final por
    cientos.

    Se usa la MEDIANA y no la media porque hay coordenadas erróneas (42 puntos
    caen fuera de Brasil, alguno en otro continente). La media los arrastraría;
    la mediana los ignora.
    """
    dentro = (
        geo["geolocation_lat"].between(*BRASIL_LAT)
        & geo["geolocation_lng"].between(*BRASIL_LNG)
    )
    geo_valida = geo[dentro]

    consolidada = (
        geo_valida.groupby("geolocation_zip_code_prefix")
        .agg(lat=("geolocation_lat", "median"), lng=("geolocation_lng", "median"))
        .reset_index()
    )
    return consolidada, int((~dentro).sum())


def resolver_resenas_duplicadas(reviews):
    """
    Deja una sola reseña por pedido.

    547 pedidos tienen dos reseñas, a veces con notas distintas (un 5 y luego
    un 4). Se conserva la MÁS RECIENTE, que es la valoración definitiva del
    cliente una vez cerrada la incidencia.
    """
    ordenadas = reviews.sort_values("review_creation_date")
    return ordenadas.drop_duplicates(subset="order_id", keep="last")


def agregar_pagos(payments):
    """
    Resume los pagos a una fila por pedido.

    Un pedido puede pagarse en varios movimientos (hasta 29 en un caso), por
    ejemplo combinando vales con tarjeta. Sin agregar, la unión duplicaría las
    líneas de pedido.

    Se conserva el importe total, el número máximo de plazos y el método
    principal, entendido como el que aporta más dinero al pedido.
    """
    resumen = payments.groupby("order_id").agg(
        importe_pagado=("payment_value", "sum"),
        plazos=("payment_installments", "max"),
        num_pagos=("payment_sequential", "count"),
    )

    # idxmax sobre el importe da la fila del método que más peso tiene en el
    # pedido; así "principal" significa algo y no es simplemente el primero.
    principal = (
        payments.loc[payments.groupby("order_id")["payment_value"].idxmax()]
        .set_index("order_id")["payment_type"]
        .rename("metodo_pago")
    )

    return resumen.join(principal).reset_index()


def distancia_haversine(lat1, lng1, lat2, lng2):
    """
    Distancia en kilómetros entre dos puntos sobre la superficie terrestre.

    No vale restar coordenadas: un grado de longitud mide distinto según la
    latitud. La fórmula de Haversine tiene en cuenta la curvatura del planeta.
    Está vectorizada con numpy para calcular las 110.000 distancias de golpe
    en lugar de recorrer el DataFrame fila a fila.
    """
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return 2 * RADIO_TIERRA_KM * np.arcsin(np.sqrt(a))


def resumen_nulos(df):
    """Tabla con el número y porcentaje de nulos por columna."""
    nulos = df.isna().sum()
    tabla = pd.DataFrame({
        "nulos": nulos,
        "porcentaje": (nulos / len(df) * 100).round(2),
        "tipo": df.dtypes.astype(str),
    })
    return tabla[tabla["nulos"] > 0].sort_values("nulos", ascending=False)


class RegistroLimpieza:
    """
    Lleva la cuenta de las decisiones de limpieza tomadas durante el proceso.

    Se usa como un cuaderno de bitácora: cada paso se anota con el problema, el
    número de filas afectadas y la decisión, y al final se vuelca a CSV. Es lo
    que permite responder meses después a "¿por qué esta columna está así?".
    """

    def __init__(self):
        self.pasos = []

    def anotar(self, problema, filas_afectadas, decision, motivo=""):
        """Añade un paso al registro y lo muestra por pantalla."""
        numero = len(self.pasos) + 1
        self.pasos.append({
            "paso": numero,
            "problema_detectado": problema,
            "filas_afectadas": filas_afectadas,
            "decision_tomada": decision,
            "justificacion": motivo,
        })
        print(f"[{numero:2d}] {problema}\n     -> {filas_afectadas} | {decision}")

    def a_dataframe(self):
        """Devuelve el registro completo como DataFrame."""
        return pd.DataFrame(self.pasos)

    def __len__(self):
        return len(self.pasos)
