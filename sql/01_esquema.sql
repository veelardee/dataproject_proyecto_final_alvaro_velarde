-- =============================================================================
-- Proyecto Final · Modelo en estrella para el análisis de ventas de Olist
-- PostgreSQL
-- =============================================================================
-- El modelo separa una tabla de HECHOS (una fila por línea de pedido, con las
-- medidas numéricas) de cinco tablas de DIMENSIÓN (los atributos por los que se
-- quiere filtrar y agrupar).
--
-- Por qué así y no una única tabla plana: el nombre "Rio de Janeiro" aparecería
-- repetido 14.000 veces en una tabla plana. En el modelo en estrella está una
-- sola vez en la dimensión y los hechos guardan solo el código. Power BI carga
-- mucho menos en memoria y las relaciones se detectan solas.
-- =============================================================================

DROP TABLE IF EXISTS hechos_ventas CASCADE;
DROP TABLE IF EXISTS dim_cliente   CASCADE;
DROP TABLE IF EXISTS dim_vendedor  CASCADE;
DROP TABLE IF EXISTS dim_producto  CASCADE;
DROP TABLE IF EXISTS dim_estado    CASCADE;
DROP TABLE IF EXISTS dim_fecha     CASCADE;


-- -----------------------------------------------------------------------------
-- DIMENSIONES
-- -----------------------------------------------------------------------------

-- Contexto socioeconómico de los 27 estados. Es la SEGUNDA FUENTE del proyecto.
CREATE TABLE dim_estado (
    estado          CHAR(2)       PRIMARY KEY,
    estado_nombre   VARCHAR(50)   NOT NULL,
    region          VARCHAR(20)   NOT NULL,
    poblacion       BIGINT        NOT NULL,
    pib_per_capita  NUMERIC(12,2),
    tasa_pobreza    NUMERIC(6,4),
    densidad        NUMERIC(10,2),
    idh             NUMERIC(5,3),
    estado_lat      NUMERIC(9,5),
    estado_lng      NUMERIC(9,5)
);

CREATE TABLE dim_cliente (
    id_cliente_unico  VARCHAR(40)  PRIMARY KEY,
    ciudad_cliente    VARCHAR(60),
    estado_cliente    CHAR(2)      REFERENCES dim_estado(estado),
    cliente_lat       NUMERIC(9,5),
    cliente_lng       NUMERIC(9,5)
);

CREATE TABLE dim_vendedor (
    id_vendedor      VARCHAR(40)  PRIMARY KEY,
    ciudad_vendedor  VARCHAR(60),
    estado_vendedor  CHAR(2)      REFERENCES dim_estado(estado),
    region_vendedor  VARCHAR(20),
    vendedor_lat     NUMERIC(9,5),
    vendedor_lng     NUMERIC(9,5)
);

CREATE TABLE dim_producto (
    id_producto  VARCHAR(40)  PRIMARY KEY,
    categoria    VARCHAR(60),
    peso_g       NUMERIC(10,2),
    largo_cm     NUMERIC(8,2),
    alto_cm      NUMERIC(8,2),
    ancho_cm     NUMERIC(8,2),
    volumen_cm3  NUMERIC(14,2),
    num_fotos    NUMERIC(5,1)
);

-- Tabla de calendario: una fila por día del periodo analizado.
-- Power BI la necesita para que la inteligencia de tiempo (acumulados,
-- comparaciones con el año anterior) funcione correctamente.
CREATE TABLE dim_fecha (
    fecha             DATE         PRIMARY KEY,
    anio              SMALLINT     NOT NULL,
    mes               SMALLINT     NOT NULL,
    nombre_mes        VARCHAR(20),
    trimestre         SMALLINT,
    dia_semana        VARCHAR(20),
    es_fin_de_semana  BOOLEAN,
    anio_mes          CHAR(7)
);


-- -----------------------------------------------------------------------------
-- TABLA DE HECHOS
-- -----------------------------------------------------------------------------
-- Grano: una fila por artículo dentro de un pedido.
-- La clave primaria es compuesta porque un mismo pedido puede tener varias
-- líneas, numeradas del 1 en adelante.
CREATE TABLE hechos_ventas (
    id_pedido                VARCHAR(40)  NOT NULL,
    num_articulo             SMALLINT     NOT NULL,
    fecha_compra             TIMESTAMP    NOT NULL,
    fecha                    DATE         REFERENCES dim_fecha(fecha),
    id_cliente_unico         VARCHAR(40)  REFERENCES dim_cliente(id_cliente_unico),
    id_vendedor              VARCHAR(40)  REFERENCES dim_vendedor(id_vendedor),
    id_producto              VARCHAR(40)  REFERENCES dim_producto(id_producto),
    estado_cliente           CHAR(2)      REFERENCES dim_estado(estado),
    estado_pedido            VARCHAR(20),

    -- Medidas económicas
    precio                   NUMERIC(10,2),
    flete                    NUMERIC(10,2),
    ingreso_linea            NUMERIC(10,2),
    peso_flete_pct           NUMERIC(10,2),
    importe_pagado           NUMERIC(10,2),
    metodo_pago              VARCHAR(20),
    plazos                   NUMERIC(4,0),   -- numérico y no entero: hay pedidos sin pago registrado

    -- Medidas logísticas
    dias_entrega_real        NUMERIC(6,1),
    dias_entrega_prometidos  NUMERIC(6,1),
    dias_retraso             NUMERIC(6,1),
    llego_tarde              NUMERIC(2,1),
    distancia_km             NUMERIC(10,1),
    mismo_estado             VARCHAR(3),

    -- Medidas de satisfacción
    nota_resena              NUMERIC(2,0),   -- puede ser nula si nadie valoró el pedido
    resena_negativa          NUMERIC(2,1),
    resena_1_estrella        NUMERIC(2,1),

    -- Dimensiones de tiempo dentro del día
    hora_compra              NUMERIC(2,0),
    franja_horaria           VARCHAR(20),

    PRIMARY KEY (id_pedido, num_articulo)
);


-- -----------------------------------------------------------------------------
-- ÍNDICES
-- -----------------------------------------------------------------------------
-- Se crean sobre las columnas por las que más se filtra y agrupa. Sin ellos,
-- cada consulta del dashboard recorrería las 112.650 filas enteras.
CREATE INDEX idx_hechos_fecha     ON hechos_ventas (fecha);
CREATE INDEX idx_hechos_estado    ON hechos_ventas (estado_cliente);
CREATE INDEX idx_hechos_vendedor  ON hechos_ventas (id_vendedor);
CREATE INDEX idx_hechos_producto  ON hechos_ventas (id_producto);
CREATE INDEX idx_hechos_tarde     ON hechos_ventas (llego_tarde);
