# Guía de construcción del dashboard en Power BI

Todo lo necesario para montar el dashboard: conexión, modelo, medidas y configuración visual por visual.

---

## 1. Conectar con PostgreSQL

Antes de nada hay que tener la base de datos cargada: ejecutar `sql/01_esquema.sql`, después `sql/02_cargar_datos.py` y por último `sql/03_vistas_analiticas.sql`.

En Power BI Desktop:

1. **Inicio → Obtener datos → Más → Base de datos → PostgreSQL**.
2. Servidor `localhost`, Base de datos `olist`.
3. Modo de conectividad: **Importar** (no DirectQuery: el conjunto cabe de sobra en memoria y así el informe va mucho más rápido).
4. Usuario `postgres` y la contraseña local.

La primera vez Power BI pedirá instalar el conector **Npgsql**. Acepta; si no aparece el aviso, se descarga de la web de Npgsql y se reinicia Power BI.

**Qué marcar en el navegador de tablas:**

| Marcar | No marcar |
|---|---|
| `hechos_ventas` | `v_kpis_generales` |
| `dim_cliente` | `v_impacto_retraso` |
| `dim_vendedor` | `v_evolucion_mensual` |
| `dim_producto` | |
| `dim_estado` | |
| `dim_fecha` | |
| `v_ventas_por_estado` | |
| `v_rendimiento_vendedores` | |
| `v_categorias` | |

Las tres vistas descartadas calculan agregados que las medidas DAX ya resuelven, y tenerlas duplicaría la información en el modelo.

---

## 2. Revisar el modelo de datos

En la pestaña **Modelo** (icono del diagrama, a la izquierda), Power BI habrá detectado algunas relaciones solo. Hay que dejarlo así:

| Desde | Hacia | Cardinalidad | Dirección |
|---|---|---|---|
| `hechos_ventas[fecha]` | `dim_fecha[fecha]` | Varios a uno | Simple |
| `hechos_ventas[id_cliente_unico]` | `dim_cliente[id_cliente_unico]` | Varios a uno | Simple |
| `hechos_ventas[id_vendedor]` | `dim_vendedor[id_vendedor]` | Varios a uno | Simple |
| `hechos_ventas[id_producto]` | `dim_producto[id_producto]` | Varios a uno | Simple |
| `hechos_ventas[estado_cliente]` | `dim_estado[estado]` | Varios a uno | Simple |

Las vistas `v_ventas_por_estado`, `v_rendimiento_vendedores` y `v_categorias` se quedan **sin relacionar**: alimentan sus propios visuales y relacionarlas crearía ambigüedad en el modelo.

**Marcar la tabla de calendario.** Selecciona `dim_fecha` → **Herramientas de tabla → Marcar como tabla de fechas** → columna `fecha`. Sin esto las funciones de inteligencia de tiempo no funcionan.

**Ocultar el ruido.** En la vista de modelo, clic derecho → Ocultar en la vista de informe sobre todas las columnas de identificador (`id_pedido`, `id_cliente_unico`, `id_vendedor`, `id_producto`). No aportan nada al usuario del informe y ensucian el panel de campos.

---

## 3. Medidas DAX

Crea una tabla vacía para agruparlas: **Inicio → Especificar datos**, nómbrala `_Medidas`, acepta con una columna vacía, y luego borra esa columna desde el editor de Power Query. Después, con la tabla seleccionada, **Nueva medida** para cada una.

### Volumen y facturación

```dax
Facturación = SUM(hechos_ventas[ingreso_linea])
```

```dax
Facturación producto = SUM(hechos_ventas[precio])
```

```dax
Facturación flete = SUM(hechos_ventas[flete])
```

```dax
Pedidos = DISTINCTCOUNT(hechos_ventas[id_pedido])
```

```dax
Clientes = DISTINCTCOUNT(hechos_ventas[id_cliente_unico])
```

```dax
Vendedores activos = DISTINCTCOUNT(hechos_ventas[id_vendedor])
```

```dax
Ticket medio = DIVIDE([Facturación], [Pedidos])
```

DIVIDE en lugar de la barra: si el denominador es cero devuelve un valor en blanco en lugar de un error que rompería el visual.

```dax
Peso del flete % = DIVIDE([Facturación flete], [Facturación producto])
```

### Calidad del servicio

```dax
Nota media = AVERAGE(hechos_ventas[nota_resena])
```

```dax
% Entregas tardías = AVERAGE(hechos_ventas[llego_tarde])
```

`llego_tarde` vale 1 o 0, así que su media es directamente la proporción. Formatéala como porcentaje.

```dax
% Reseñas de 1 estrella = AVERAGE(hechos_ventas[resena_1_estrella])
```

```dax
% Reseñas negativas = AVERAGE(hechos_ventas[resena_negativa])
```

```dax
Días de entrega = AVERAGE(hechos_ventas[dias_entrega_real])
```

```dax
Días prometidos = AVERAGE(hechos_ventas[dias_entrega_prometidos])
```

```dax
Holgura del plazo = [Días prometidos] - [Días de entrega]
```

```dax
Distancia media = AVERAGE(hechos_ventas[distancia_km])
```

### El impacto del retraso

```dax
Nota si llega a tiempo =
CALCULATE([Nota media], hechos_ventas[llego_tarde] = 0)
```

```dax
Nota si llega tarde =
CALCULATE([Nota media], hechos_ventas[llego_tarde] = 1)
```

```dax
Coste del retraso en nota = [Nota si llega a tiempo] - [Nota si llega tarde]
```

```dax
Facturación en riesgo =
CALCULATE([Facturación], hechos_ventas[llego_tarde] = 1)
```

```dax
Vendedores críticos =
CALCULATE(
    DISTINCTCOUNT(v_rendimiento_vendedores[id_vendedor]),
    v_rendimiento_vendedores[semaforo] = "Crítico"
)
```

### Evolución temporal

```dax
Facturación año anterior =
CALCULATE([Facturación], SAMEPERIODLASTYEAR(dim_fecha[fecha]))
```

```dax
Variación interanual % =
VAR Actual = [Facturación]
VAR Anterior = [Facturación año anterior]
RETURN DIVIDE(Actual - Anterior, Anterior)
```

Se usan variables (`VAR`) en lugar de repetir las medidas dentro del DIVIDE: DAX las evalúa una sola vez en lugar de dos, y la fórmula se lee mucho mejor.

```dax
Facturación acumulada =
CALCULATE([Facturación], DATESYTD(dim_fecha[fecha]))
```

### Penetración comercial

```dax
Población alcanzada = SUM(dim_estado[poblacion])
```

```dax
Gasto por habitante = DIVIDE([Facturación], [Población alcanzada])
```

```dax
Clientes por 10.000 habitantes =
DIVIDE([Clientes], [Población alcanzada]) * 10000
```

### Formato condicional

```dax
Color del semáforo =
SWITCH(
    TRUE(),
    [% Entregas tardías] > 0.15, "#e34948",
    [% Entregas tardías] > 0.08, "#eda100",
    "#1baf7a"
)
```

Se usa en **Formato → Color de fuente → fx → Formato por → Valor del campo**, eligiendo esta medida.

---

## 4. Paleta y estilo

Colores comprobados para que sigan distinguiéndose con daltonismo:

| Uso | Color |
|---|---|
| Serie principal | `#2a78d6` |
| Contraste / alerta | `#eb6834` |
| Positivo | `#1baf7a` |
| Aviso | `#eda100` |
| Crítico | `#e34948` |
| Texto | `#0b0b0b` |
| Texto secundario | `#52514e` |
| Fondo de página | `#f7f7f5` |

**Vista → Tema → Personalizar tema actual** para cargarlos de una vez y que todos los visuales los hereden.

Tres reglas que marcan la diferencia:

- **Sin bordes ni sombras** en los visuales: solo fondo blanco y esquinas redondeadas a 8 px.
- **Cuadrícula tenue**, gris `#e8e7e2`, y nunca líneas verticales y horizontales a la vez.
- **Un solo eje por gráfico.** Nada de doble eje vertical: si hay dos medidas de escalas distintas, se hacen dos gráficos.

---

## 5. Las tres páginas

### Página 1 · Visión general

Para dirección: cómo va el negocio.

**Fila superior, cinco tarjetas** (visual *Tarjeta*): Facturación, Pedidos, Clientes, Nota media y % Entregas tardías.

**Gráfico de áreas** — Evolución mensual
Eje X `dim_fecha[anio_mes]`, eje Y `[Facturación]`. Activa la línea de tendencia en Analítica.

**Mapa** — Distribución geográfica
Visual *Mapa*. Latitud `dim_estado[estado_lat]`, Longitud `dim_estado[estado_lng]`, Tamaño de burbuja `[Facturación]`, Leyenda `dim_estado[region]`.

**Gráfico de barras horizontales** — Top 10 categorías
Eje Y `dim_producto[categoria]`, eje X `[Facturación]`. En Filtros del visual: Filtrado N superior = 10 por Facturación.

**Gráfico de columnas** — Distribución de las notas
Eje X `hechos_ventas[nota_resena]`, eje Y Recuento. Colorea de rojo las columnas 1 y 2.

**Segmentaciones** en una franja a la izquierda: Año, Región, Categoría. Todas en formato desplegable para no comerse la página.

### Página 2 · Calidad del servicio

Para operaciones: dónde está el problema.

**Cuatro tarjetas**: % Entregas tardías, Días de entrega, Nota si llega a tiempo, Nota si llega tarde. Las dos últimas, juntas, cuentan la historia entera.

**Gráfico de columnas** — El gradiente del retraso
Es el visual más importante del informe. Eje X `v_impacto_retraso[tramo_retraso]`, eje Y `v_impacto_retraso[nota_media]`. Colorea de azul los tres primeros tramos y de naranja los cuatro últimos.

**Gráfico de columnas** — % de 1 estrella por tramo
Mismo eje X, eje Y `pct_una_estrella`. Al lado del anterior.

**Gráfico de barras** — Plazo por región
Eje Y `dim_estado[region]`, eje X `[Días de entrega]`.

**Gráfico de dispersión** — Vendedores
Eje X `v_rendimiento_vendedores[pct_entregas_tardias]`, eje Y `nota_media`, Tamaño `facturacion`, Leyenda `semaforo`. Este visual identifica de un vistazo a los veinte vendedores problemáticos.

**Tabla** — Vendedores críticos
Columnas: vendedor, estado, pedidos, facturación, % tardías, nota. Filtro del visual: `semaforo` es "Crítico". Aplica el formato condicional del semáforo sobre la columna de porcentaje.

### Página 3 · Oportunidad comercial

Para el equipo comercial: dónde crecer.

**Tres tarjetas**: Gasto por habitante, Clientes por 10.000 habitantes, Estados cubiertos.

**Gráfico de dispersión** — Penetración frente a desarrollo
Eje X `v_ventas_por_estado[idh]`, eje Y `gasto_por_habitante`, Tamaño `poblacion`, Detalles `estado`. En **Analítica → Línea de tendencia**, actívala: los estados por debajo de la recta son la oportunidad.

**Mapa** — Penetración por estado
Igual que el de la página 1 pero con Tamaño de burbuja `gasto_por_habitante` y color por `pct_entregas_tardias`. Deja ver que los estados con menos penetración son los que peor servicio reciben.

**Tabla** — Estados ordenados por recorrido
Columnas: estado, facturación, gasto por habitante, puesto de penetración, % tardías, días de entrega.

**Gráfico de barras** — Días de entrega por estado
Ordenado de mayor a menor. Los seis primeros son los estados con más potencial sin captar.

---

## 6. Antes de dar por cerrado el informe

- **Comprueba los totales**: la facturación debe dar 15.843.553 R$ y los pedidos 98.666. Si no cuadra, algo falla en las relaciones del modelo.
- **Prueba los filtros**: selecciona un año y comprueba que las tres páginas responden.
- **Añade botones de navegación** entre páginas: Insertar → Botones → Navegador de páginas.
- **Títulos que digan algo.** "Llegar tarde hunde la valoración" comunica mucho más que "Nota media por tramo de retraso".
- **Exporta a PDF** (Archivo → Exportar → PDF) y guarda capturas de cada página en `powerbi/capturas/` para el README.
