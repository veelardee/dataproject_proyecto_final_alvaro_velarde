"""
Carga el modelo en estrella en PostgreSQL.

Lee los CSV comprimidos que genera el notebook 01 y los vuelca en la base de
datos creada con 01_esquema.sql. Power BI se conecta después a esta base, no a
los ficheros sueltos.

Uso:
    python sql/02_cargar_datos.py

Requiere:
    pip install pandas sqlalchemy psycopg2-binary

Alternativa sin instalar nada, desde psql: descomprimir antes los CSV y usar
\\copy tabla FROM 'ruta.csv' WITH (FORMAT csv, HEADER true), respetando el
mismo orden de carga que la lista ORDEN_CARGA de más abajo.
"""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# -----------------------------------------------------------------------------
# Configuración de la conexión
# -----------------------------------------------------------------------------
USUARIO = "postgres"
CLAVE = "postgres"          # cambiar por la contraseña local
SERVIDOR = "localhost"
PUERTO = 5432
BASE_DATOS = "olist"

CADENA_CONEXION = f"postgresql+psycopg2://{USUARIO}:{CLAVE}@{SERVIDOR}:{PUERTO}/{BASE_DATOS}"

RUTA_MODELO = Path(__file__).parent.parent / "data" / "processed" / "modelo_estrella"

# El orden importa: las dimensiones primero, porque la tabla de hechos tiene
# claves ajenas que apuntan a ellas y fallaría si aún no existen sus filas.
ORDEN_CARGA = [
    "dim_estado",
    "dim_cliente",
    "dim_vendedor",
    "dim_producto",
    "dim_fecha",
    "hechos_ventas",
]


def cargar_tabla(motor, nombre, ruta):
    """Vuelca un CSV comprimido en su tabla de PostgreSQL."""
    df = pd.read_csv(ruta)

    # La tabla de hechos tiene columnas que no están en el esquema (se
    # generaron para el análisis pero no se guardan en la base).
    if nombre == "hechos_ventas":
        with motor.connect() as conexion:
            columnas_destino = pd.read_sql(
                text("SELECT * FROM hechos_ventas LIMIT 0"), conexion
            ).columns.tolist()
        df = df[[c for c in columnas_destino if c in df.columns]]

    # method="multi" agrupa varias filas por sentencia INSERT. Sin esto, cargar
    # las 112.650 filas de hechos tarda varios minutos en lugar de segundos.
    df.to_sql(nombre, motor, if_exists="append", index=False,
              method="multi", chunksize=5000)

    return len(df)


def main():
    if not RUTA_MODELO.exists():
        sys.exit(f"No se encuentra {RUTA_MODELO}. Ejecuta antes el notebook 01.")

    motor = create_engine(CADENA_CONEXION)

    print("Cargando el modelo en estrella en PostgreSQL\n")
    total = 0
    for nombre in ORDEN_CARGA:
        ruta = RUTA_MODELO / f"{nombre}.csv.gz"
        filas = cargar_tabla(motor, nombre, ruta)
        total += filas
        print(f"  {nombre:<16} {filas:>8,} filas")

    print(f"\n  {'TOTAL':<16} {total:>8,} filas cargadas")

    # Comprobación: contar lo que ha quedado realmente en la base
    print("\nVerificación desde la base de datos:")
    with motor.connect() as conexion:
        for nombre in ORDEN_CARGA:
            n = conexion.execute(text(f"SELECT COUNT(*) FROM {nombre}")).scalar()
            print(f"  {nombre:<16} {n:>8,}")


if __name__ == "__main__":
    main()
