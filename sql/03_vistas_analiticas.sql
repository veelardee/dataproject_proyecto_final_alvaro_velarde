-- =============================================================================
-- Proyecto Final · Vistas analíticas sobre el modelo en estrella
-- =============================================================================
-- Estas vistas resuelven en la base de datos los cálculos que se repiten en el
-- dashboard. Power BI se conecta a ellas en lugar de a las tablas en bruto, de
-- forma que la lógica de negocio vive en un único sitio y no duplicada en cada
-- informe que alguien construya después.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Indicadores generales del negocio
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_kpis_generales AS
SELECT
    COUNT(*)                                        AS lineas_pedido,
    COUNT(DISTINCT id_pedido)                       AS pedidos,
    COUNT(DISTINCT id_cliente_unico)                AS clientes,
    COUNT(DISTINCT id_vendedor)                     AS vendedores,
    ROUND(SUM(ingreso_linea), 2)                    AS facturacion,
    ROUND(SUM(precio), 2)                           AS facturacion_producto,
    ROUND(SUM(flete), 2)                            AS facturacion_flete,
    ROUND(AVG(nota_resena), 3)                      AS nota_media,
    ROUND(AVG(dias_entrega_real), 2)                AS dias_entrega_medios,
    ROUND(AVG(llego_tarde) * 100, 2)                AS pct_entregas_tardias,
    ROUND(AVG(resena_1_estrella) * 100, 2)          AS pct_una_estrella
FROM hechos_ventas;


-- -----------------------------------------------------------------------------
-- 2. Ventas por estado con penetración sobre la población
-- -----------------------------------------------------------------------------
-- Es la vista que cruza las DOS FUENTES: las ventas de Olist con los datos
-- demográficos del instituto estadístico. Sin la segunda fuente no se podría
-- calcular el gasto por habitante, que es lo que permite comparar estados de
-- tamaños muy distintos.
CREATE OR REPLACE VIEW v_ventas_por_estado AS
WITH ventas AS (
    SELECT
        h.estado_cliente,
        COUNT(DISTINCT h.id_pedido)       AS pedidos,
        COUNT(DISTINCT h.id_cliente_unico) AS clientes,
        SUM(h.ingreso_linea)              AS facturacion,
        AVG(h.nota_resena)                AS nota_media,
        AVG(h.llego_tarde)                AS tasa_retraso,
        AVG(h.dias_entrega_real)          AS dias_entrega,
        AVG(h.distancia_km)               AS distancia_media,
        AVG(h.peso_flete_pct)             AS peso_flete
    FROM hechos_ventas AS h
    GROUP BY h.estado_cliente
)
SELECT
    e.estado,
    e.estado_nombre,
    e.region,
    e.poblacion,
    e.pib_per_capita,
    e.idh,
    e.tasa_pobreza,
    e.estado_lat,
    e.estado_lng,
    v.pedidos,
    v.clientes,
    ROUND(v.facturacion, 2)                                   AS facturacion,
    ROUND(v.facturacion / e.poblacion, 4)                     AS gasto_por_habitante,
    ROUND(v.clientes::NUMERIC / e.poblacion * 10000, 2)       AS clientes_por_10k_hab,
    ROUND(v.nota_media, 3)                                    AS nota_media,
    ROUND(v.tasa_retraso * 100, 2)                            AS pct_entregas_tardias,
    ROUND(v.dias_entrega, 1)                                  AS dias_entrega,
    ROUND(v.distancia_media, 1)                               AS distancia_media_km,
    ROUND(v.peso_flete, 1)                                    AS peso_flete_pct,
    -- El ranking permite ordenar en el dashboard sin recalcularlo cada vez
    RANK() OVER (ORDER BY v.facturacion DESC)                 AS puesto_facturacion,
    RANK() OVER (ORDER BY v.facturacion / e.poblacion DESC)   AS puesto_penetracion
FROM dim_estado AS e
INNER JOIN ventas AS v
    ON e.estado = v.estado_cliente;


-- -----------------------------------------------------------------------------
-- 3. Rendimiento de los vendedores
-- -----------------------------------------------------------------------------
-- Solo se consideran los vendedores con 50 pedidos o más: por debajo de ese
-- volumen la tasa de retraso es ruido estadístico (un vendedor con 3 pedidos y
-- 1 tardío tendría un 33% que no significa nada).
CREATE OR REPLACE VIEW v_rendimiento_vendedores AS
WITH metricas AS (
    SELECT
        v.id_vendedor,
        v.ciudad_vendedor,
        v.estado_vendedor,
        v.region_vendedor,
        v.vendedor_lat,
        v.vendedor_lng,
        COUNT(DISTINCT h.id_pedido)   AS pedidos,
        SUM(h.ingreso_linea)          AS facturacion,
        AVG(h.nota_resena)            AS nota_media,
        AVG(h.llego_tarde)            AS tasa_retraso,
        AVG(h.dias_entrega_real)      AS dias_entrega,
        AVG(h.resena_1_estrella)      AS tasa_una_estrella
    FROM hechos_ventas AS h
    INNER JOIN dim_vendedor AS v
        ON h.id_vendedor = v.id_vendedor
    WHERE h.estado_pedido = 'delivered'
    GROUP BY v.id_vendedor, v.ciudad_vendedor, v.estado_vendedor,
             v.region_vendedor, v.vendedor_lat, v.vendedor_lng
    HAVING COUNT(DISTINCT h.id_pedido) >= 50
)
SELECT
    id_vendedor,
    ciudad_vendedor,
    estado_vendedor,
    region_vendedor,
    vendedor_lat,
    vendedor_lng,
    pedidos,
    ROUND(facturacion, 2)            AS facturacion,
    ROUND(nota_media, 3)             AS nota_media,
    ROUND(tasa_retraso * 100, 2)     AS pct_entregas_tardias,
    ROUND(tasa_una_estrella * 100, 2) AS pct_una_estrella,
    ROUND(dias_entrega, 1)           AS dias_entrega,
    -- Semáforo para el dashboard: el umbral del 15% sale del análisis
    CASE
        WHEN tasa_retraso > 0.15 THEN 'Crítico'
        WHEN tasa_retraso > 0.08 THEN 'Vigilar'
        ELSE 'Correcto'
    END                              AS semaforo,
    -- NTILE reparte a los vendedores en cuatro grupos según su facturación
    NTILE(4) OVER (ORDER BY facturacion DESC) AS cuartil_facturacion
FROM metricas;


-- -----------------------------------------------------------------------------
-- 4. Impacto del retraso sobre la valoración
-- -----------------------------------------------------------------------------
-- Reproduce en SQL el hallazgo central del análisis, para que el dashboard no
-- dependa de que alguien recuerde cómo se calculó.
CREATE OR REPLACE VIEW v_impacto_retraso AS
SELECT
    CASE
        WHEN dias_retraso <= -10 THEN '1. Más de 10 días antes'
        WHEN dias_retraso <   -5 THEN '2. Entre 5 y 10 días antes'
        WHEN dias_retraso <=   0 THEN '3. Hasta 5 días antes'
        WHEN dias_retraso <=   3 THEN '4. De 1 a 3 días tarde'
        WHEN dias_retraso <=   7 THEN '5. De 4 a 7 días tarde'
        WHEN dias_retraso <=  15 THEN '6. De 8 a 15 días tarde'
        ELSE                          '7. Más de 15 días tarde'
    END                                     AS tramo_retraso,
    COUNT(*)                                AS pedidos,
    ROUND(AVG(nota_resena), 3)              AS nota_media,
    ROUND(AVG(resena_1_estrella) * 100, 2)  AS pct_una_estrella,
    ROUND(AVG(resena_negativa) * 100, 2)    AS pct_negativas,
    ROUND(SUM(ingreso_linea), 2)            AS facturacion
FROM hechos_ventas
WHERE estado_pedido = 'delivered'
  AND nota_resena IS NOT NULL
  AND dias_retraso IS NOT NULL
GROUP BY tramo_retraso;


-- -----------------------------------------------------------------------------
-- 5. Evolución mensual con media móvil
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_evolucion_mensual AS
WITH mensual AS (
    SELECT
        f.anio_mes,
        MIN(f.fecha)                    AS primer_dia,
        COUNT(DISTINCT h.id_pedido)     AS pedidos,
        SUM(h.ingreso_linea)            AS facturacion,
        AVG(h.nota_resena)              AS nota_media,
        AVG(h.llego_tarde)              AS tasa_retraso
    FROM hechos_ventas AS h
    INNER JOIN dim_fecha AS f
        ON h.fecha = f.fecha
    GROUP BY f.anio_mes
)
SELECT
    anio_mes,
    primer_dia,
    pedidos,
    ROUND(facturacion, 2)         AS facturacion,
    ROUND(nota_media, 3)          AS nota_media,
    ROUND(tasa_retraso * 100, 2)  AS pct_entregas_tardias,
    -- Media móvil de tres meses para suavizar el ruido mensual
    ROUND(AVG(facturacion) OVER (
        ORDER BY primer_dia ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2)                         AS facturacion_media_movil_3m,
    -- Variación frente al mes anterior
    ROUND((facturacion / NULLIF(LAG(facturacion) OVER (ORDER BY primer_dia), 0) - 1)
          * 100, 2)               AS variacion_mensual_pct
FROM mensual;


-- -----------------------------------------------------------------------------
-- 6. Rendimiento por categoría de producto
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_categorias AS
SELECT
    p.categoria,
    COUNT(*)                                AS lineas,
    COUNT(DISTINCT h.id_pedido)             AS pedidos,
    ROUND(SUM(h.ingreso_linea), 2)          AS facturacion,
    ROUND(AVG(h.precio), 2)                 AS precio_medio,
    ROUND(AVG(h.peso_flete_pct), 1)         AS peso_flete_pct,
    ROUND(AVG(p.peso_g) / 1000, 2)          AS peso_medio_kg,
    ROUND(AVG(h.nota_resena), 3)            AS nota_media,
    ROUND(AVG(h.llego_tarde) * 100, 2)      AS pct_entregas_tardias,
    -- Cuota sobre el total, calculada con una función de ventana en lugar de
    -- con una subconsulta que recorrería la tabla otra vez
    ROUND(SUM(h.ingreso_linea) * 100.0 / SUM(SUM(h.ingreso_linea)) OVER (), 2)
                                            AS cuota_facturacion_pct
FROM hechos_ventas AS h
INNER JOIN dim_producto AS p
    ON h.id_producto = p.id_producto
GROUP BY p.categoria
HAVING COUNT(*) >= 100;
