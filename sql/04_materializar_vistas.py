"""Materializa en CSV las seis vistas analíticas de 03_vistas_analiticas.sql.

Por qué existe este script
--------------------------
Las vistas viven en PostgreSQL, que es donde deben vivir: la lógica de negocio
en un solo sitio y no duplicada en cada informe. Pero eso obliga a tener el
servidor levantado para poder abrir el dashboard, y a quien se descargue el
repositorio para revisarlo no se le puede pedir que instale una base de datos.

Este script calcula exactamente las mismas seis vistas con pandas y las deja
como CSV en data/processed/vistas/, que es de donde las lee Power BI. Los
resultados son idénticos a los de las vistas SQL: los umbrales (50 pedidos
mínimos por vendedor, 100 líneas mínimas por categoría), los tramos de retraso
y los redondeos están replicados uno a uno.

Uso
---
    python sql/04_materializar_vistas.py

Requiere haber ejecutado antes notebooks/01_limpieza_y_union.ipynb, que es lo
que genera data/processed/modelo_estrella/.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Las rutas se resuelven desde la raíz del repositorio, no desde el directorio
# donde se lance el script, para que funcione igual desde cualquier sitio.
RAIZ = Path(__file__).resolve().parent.parent
ESTRELLA = RAIZ / "data" / "processed" / "modelo_estrella"
SALIDA = RAIZ / "data" / "processed" / "vistas"


def redondear(serie, decimales):
    return np.round(serie, decimales)


def cargar():
    hechos = pd.read_csv(
        ESTRELLA / "hechos_ventas.csv.gz", parse_dates=["fecha", "fecha_compra"]
    )
    dims = {
        nombre: pd.read_csv(
            ESTRELLA / f"{nombre}.csv.gz",
            parse_dates=["fecha"] if nombre == "dim_fecha" else None,
        )
        for nombre in ("dim_estado", "dim_vendedor", "dim_producto", "dim_fecha")
    }
    return hechos, dims


def v_kpis_generales(h):
    """Indicadores generales. Son los totales de control del proyecto."""
    return pd.DataFrame([{
        "lineas_pedido": len(h),
        "pedidos": h.id_pedido.nunique(),
        "clientes": h.id_cliente_unico.nunique(),
        "vendedores": h.id_vendedor.nunique(),
        "facturacion": round(h.ingreso_linea.sum(), 2),
        "facturacion_producto": round(h.precio.sum(), 2),
        "facturacion_flete": round(h.flete.sum(), 2),
        "nota_media": round(h.nota_resena.mean(), 3),
        "dias_entrega_medios": round(h.dias_entrega_real.mean(), 2),
        "pct_entregas_tardias": round(h.llego_tarde.mean() * 100, 2),
        "pct_una_estrella": round(h.resena_1_estrella.mean() * 100, 2),
    }])


def v_ventas_por_estado(h, dim_estado):
    """Cruza las DOS fuentes: ventas de Olist y demografía del instituto.

    Sin la segunda fuente no se podría calcular el gasto por habitante, que es
    lo único que permite comparar estados de tamaños tan distintos como São
    Paulo y Roraima.
    """
    v = h.groupby("estado_cliente").agg(
        pedidos=("id_pedido", "nunique"),
        clientes=("id_cliente_unico", "nunique"),
        facturacion=("ingreso_linea", "sum"),
        nota_media=("nota_resena", "mean"),
        tasa_retraso=("llego_tarde", "mean"),
        dias_entrega=("dias_entrega_real", "mean"),
        distancia_media=("distancia_km", "mean"),
        peso_flete=("peso_flete_pct", "mean"),
    ).reset_index()

    e = dim_estado.merge(v, left_on="estado", right_on="estado_cliente", how="inner")
    salida = pd.DataFrame({
        "estado": e.estado,
        "estado_nombre": e.estado_nombre,
        "region": e.region,
        "poblacion": e.poblacion,
        "pib_per_capita": e.pib_per_capita,
        "idh": e.idh,
        "tasa_pobreza": e.tasa_pobreza,
        "estado_lat": e.estado_lat,
        "estado_lng": e.estado_lng,
        "pedidos": e.pedidos,
        "clientes": e.clientes,
        "facturacion": redondear(e.facturacion, 2),
        "gasto_por_habitante": redondear(e.facturacion / e.poblacion, 4),
        "clientes_por_10k_hab": redondear(e.clientes / e.poblacion * 10000, 2),
        "nota_media": redondear(e.nota_media, 3),
        "pct_entregas_tardias": redondear(e.tasa_retraso * 100, 2),
        "dias_entrega": redondear(e.dias_entrega, 1),
        "distancia_media_km": redondear(e.distancia_media, 1),
        "peso_flete_pct": redondear(e.peso_flete, 1),
    })
    # Equivalente a RANK() OVER (ORDER BY ... DESC): method="min" reproduce el
    # comportamiento de SQL ante empates (mismo puesto, siguiente salta).
    salida["puesto_facturacion"] = e.facturacion.rank(
        ascending=False, method="min").astype(int)
    salida["puesto_penetracion"] = (e.facturacion / e.poblacion).rank(
        ascending=False, method="min").astype(int)
    return salida.sort_values("puesto_facturacion")


def v_rendimiento_vendedores(h, dim_vendedor):
    """Solo vendedores con 50 pedidos o más.

    Por debajo de ese volumen la tasa de retraso es ruido estadístico: un
    vendedor con 3 pedidos y 1 tardío tendría un 33% que no significa nada.
    """
    entregados = h[h.estado_pedido == "delivered"]
    claves = ["id_vendedor", "ciudad_vendedor", "estado_vendedor",
              "region_vendedor", "vendedor_lat", "vendedor_lng"]
    m = entregados.merge(dim_vendedor, on="id_vendedor", how="inner").groupby(
        claves, dropna=False).agg(
        pedidos=("id_pedido", "nunique"),
        facturacion=("ingreso_linea", "sum"),
        nota_media=("nota_resena", "mean"),
        tasa_retraso=("llego_tarde", "mean"),
        dias_entrega=("dias_entrega_real", "mean"),
        tasa_una_estrella=("resena_1_estrella", "mean"),
    ).reset_index()
    m = m[m.pedidos >= 50].copy()

    salida = pd.DataFrame({
        "id_vendedor": m.id_vendedor,
        "ciudad_vendedor": m.ciudad_vendedor,
        "estado_vendedor": m.estado_vendedor,
        "region_vendedor": m.region_vendedor,
        "vendedor_lat": m.vendedor_lat,
        "vendedor_lng": m.vendedor_lng,
        "pedidos": m.pedidos,
        "facturacion": redondear(m.facturacion, 2),
        "nota_media": redondear(m.nota_media, 3),
        "pct_entregas_tardias": redondear(m.tasa_retraso * 100, 2),
        "pct_una_estrella": redondear(m.tasa_una_estrella * 100, 2),
        "dias_entrega": redondear(m.dias_entrega, 1),
        # El umbral del 15% sale del análisis, no de una cifra redonda
        "semaforo": np.select(
            [m.tasa_retraso > 0.15, m.tasa_retraso > 0.08],
            ["Crítico", "Vigilar"], default="Correcto"),
    })
    # Equivalente a NTILE(4) OVER (ORDER BY facturacion DESC)
    salida["cuartil_facturacion"] = pd.qcut(
        m.facturacion.rank(ascending=False, method="first"),
        4, labels=[1, 2, 3, 4]).astype(int)
    return salida.sort_values("facturacion", ascending=False)


def v_impacto_retraso(h):
    """El hallazgo central del análisis, reproducido tramo a tramo."""
    base = h[(h.estado_pedido == "delivered")
             & h.nota_resena.notna()
             & h.dias_retraso.notna()].copy()
    # np.select evalúa en orden, igual que el CASE WHEN de SQL
    base["tramo_retraso"] = np.select(
        [base.dias_retraso <= -10, base.dias_retraso < -5, base.dias_retraso <= 0,
         base.dias_retraso <= 3, base.dias_retraso <= 7, base.dias_retraso <= 15],
        ["1. Más de 10 días antes", "2. Entre 5 y 10 días antes",
         "3. Hasta 5 días antes", "4. De 1 a 3 días tarde",
         "5. De 4 a 7 días tarde", "6. De 8 a 15 días tarde"],
        default="7. Más de 15 días tarde")

    imp = base.groupby("tramo_retraso").agg(
        pedidos=("id_pedido", "size"),
        nota_media=("nota_resena", "mean"),
        pct_una_estrella=("resena_1_estrella", "mean"),
        pct_negativas=("resena_negativa", "mean"),
        facturacion=("ingreso_linea", "sum"),
    ).reset_index()
    imp["nota_media"] = redondear(imp.nota_media, 3)
    imp["pct_una_estrella"] = redondear(imp.pct_una_estrella * 100, 2)
    imp["pct_negativas"] = redondear(imp.pct_negativas * 100, 2)
    imp["facturacion"] = redondear(imp.facturacion, 2)
    # El prefijo numérico del tramo es lo que mantiene el orden en el dashboard
    return imp.sort_values("tramo_retraso")


def v_evolucion_mensual(h, dim_fecha):
    hf = h.merge(dim_fecha[["fecha", "anio_mes"]], on="fecha", how="inner")
    mes = hf.groupby("anio_mes").agg(
        primer_dia=("fecha", "min"),
        pedidos=("id_pedido", "nunique"),
        facturacion=("ingreso_linea", "sum"),
        nota_media=("nota_resena", "mean"),
        tasa_retraso=("llego_tarde", "mean"),
    ).reset_index().sort_values("primer_dia")

    # rolling(3) equivale a ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    mes["facturacion_media_movil_3m"] = redondear(
        mes.facturacion.rolling(3, min_periods=1).mean(), 2)
    # shift(1) equivale a LAG(facturacion) OVER (ORDER BY primer_dia)
    mes["variacion_mensual_pct"] = redondear(
        (mes.facturacion / mes.facturacion.shift(1) - 1) * 100, 2)
    mes["facturacion"] = redondear(mes.facturacion, 2)
    mes["nota_media"] = redondear(mes.nota_media, 3)
    mes["pct_entregas_tardias"] = redondear(mes.tasa_retraso * 100, 2)
    return mes.drop(columns=["tasa_retraso"])


def v_categorias(h, dim_producto):
    """Categorías con 100 líneas o más, con su cuota sobre el total."""
    hp = h.merge(dim_producto[["id_producto", "categoria", "peso_g"]],
                 on="id_producto", how="inner")
    cat = hp.groupby("categoria").agg(
        lineas=("id_pedido", "size"),
        pedidos=("id_pedido", "nunique"),
        facturacion=("ingreso_linea", "sum"),
        precio_medio=("precio", "mean"),
        peso_flete_pct=("peso_flete_pct", "mean"),
        peso_medio_kg=("peso_g", "mean"),
        nota_media=("nota_resena", "mean"),
        pct_entregas_tardias=("llego_tarde", "mean"),
    ).reset_index()
    cat = cat[cat.lineas >= 100].copy()

    # La cuota se calcula sobre el total ya filtrado, igual que la función de
    # ventana SUM(SUM(...)) OVER () de la vista SQL
    cat["cuota_facturacion_pct"] = redondear(
        cat.facturacion * 100.0 / cat.facturacion.sum(), 2)
    cat["facturacion"] = redondear(cat.facturacion, 2)
    cat["precio_medio"] = redondear(cat.precio_medio, 2)
    cat["peso_flete_pct"] = redondear(cat.peso_flete_pct, 1)
    cat["peso_medio_kg"] = redondear(cat.peso_medio_kg / 1000, 2)
    cat["nota_media"] = redondear(cat.nota_media, 3)
    cat["pct_entregas_tardias"] = redondear(cat.pct_entregas_tardias * 100, 2)
    return cat.sort_values("facturacion", ascending=False)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    hechos, dims = cargar()

    vistas = {
        "v_kpis_generales": v_kpis_generales(hechos),
        "v_ventas_por_estado": v_ventas_por_estado(hechos, dims["dim_estado"]),
        "v_rendimiento_vendedores": v_rendimiento_vendedores(hechos, dims["dim_vendedor"]),
        "v_impacto_retraso": v_impacto_retraso(hechos),
        "v_evolucion_mensual": v_evolucion_mensual(hechos, dims["dim_fecha"]),
        "v_categorias": v_categorias(hechos, dims["dim_producto"]),
    }

    for nombre, tabla in vistas.items():
        destino = SALIDA / f"{nombre}.csv"
        tabla.to_csv(destino, index=False)
        print(f"{nombre:26} {len(tabla):>5} filas  ->  {destino.relative_to(RAIZ)}")

    kpis = vistas["v_kpis_generales"].iloc[0]
    print("\nTotales de control:")
    print(f"  Facturación  {kpis.facturacion:,.2f} R$")
    print(f"  Pedidos      {kpis.pedidos:,}")
    print(f"  Clientes     {kpis.clientes:,}")
    print(f"  Nota media   {kpis.nota_media}")


if __name__ == "__main__":
    main()
