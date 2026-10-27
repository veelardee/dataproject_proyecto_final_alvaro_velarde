# Guía de construcción del dashboard en Power BI

Todo lo necesario para montar `dashboard_olist.pbix` desde cero: carga de datos, modelo, medidas, tema y la posición exacta de cada visual.

El dashboard se alimenta de la capa `data/processed/`, que es la salida del notebook `01_limpieza_y_union.ipynb`. No hace falta tener PostgreSQL levantado: las seis vistas analíticas de `sql/03_vistas_analiticas.sql` están materializadas en `data/processed/vistas/` con exactamente la misma lógica, de modo que el informe se puede reproducir con solo clonar el repositorio. Al final de esta guía está la alternativa para conectar contra PostgreSQL si se prefiere la ruta de base de datos.

---

## 1. Cargar los datos con Power Query

Los archivos del modelo en estrella están comprimidos en `.csv.gz` para que el repositorio no se dispare de tamaño. Power BI no los abre desde **Obtener datos → Texto/CSV**, pero sí desde Power Query descomprimiéndolos al vuelo. Se hace una vez y queda resuelto.

Hay además una razón de fondo para cargar así en lugar de por la interfaz: definiendo los tipos a mano con la referencia `"en-US"` se evita que un Windows en español interprete `4.033` como cuatro mil treinta y tres. Es el error silencioso más habitual al importar CSV, y aquí queda cerrado de raíz.

### 1.1 La ruta de los datos

**Inicio → Transformar datos** para abrir Power Query. Dentro: **Inicio → Nuevo origen → Consulta en blanco**, y en **Ver → Editor avanzado** pega esto, cambiando la ruta por la de tu carpeta:

```m
let
    Ruta = "C:\Users\TU_USUARIO\Documents\GitHub\dataproject_proyecto_final_alvaro_velarde\data\processed\"
in
    Ruta
```

Renómbrala `RutaDatos` en el panel de la derecha. La barra final es obligatoria.

Es el único sitio de todo el informe donde aparece una ruta absoluta: quien se descargue el repositorio solo tiene que cambiar esta línea para que las once consultas vuelvan a funcionar.

Ahora, **clic derecho sobre `RutaDatos` → desmarcar «Habilitar carga»**. Es una consulta auxiliar, no una tabla del modelo, y si se carga aparece como una tabla fantasma con un único valor.

### 1.2 La función que lee los archivos

Otra **consulta en blanco**, y en el Editor avanzado:

```m
let
    LeerCsv = (archivo as text, tipos as list) =>
        let
            binario   = File.Contents(RutaDatos & archivo),
            // Los .csv.gz se descomprimen en memoria; los .csv entran tal cual
            contenido = if Text.EndsWith(archivo, ".gz")
                        then Binary.Decompress(binario, Compression.GZip)
                        else binario,
            csv       = Csv.Document(contenido, [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
            cabeceras = Table.PromoteHeaders(csv, [PromoteAllScalars = true]),
            // El "en-US" del final es lo que fija el punto como separador decimal
            tipado    = Table.TransformColumnTypes(cabeceras, tipos, "en-US")
        in
            tipado
in
    LeerCsv
```

Renómbrala `LeerCsv`. Las funciones no se cargan al modelo, así que aquí no hay que desmarcar nada.

### 1.3 Las once tablas

Para cada una: **Nuevo origen → Consulta en blanco → Editor avanzado**, pegar el bloque, y renombrar la consulta con el nombre del encabezado. Son once pegadas seguidas y es la parte más mecánica de todo el proceso.

#### `hechos_ventas`

```m
let
    t = LeerCsv("modelo_estrella\hechos_ventas.csv.gz", {
        {"id_pedido", type text}, {"num_articulo", Int64.Type}, {"fecha_compra", type datetime},
        {"id_cliente_unico", type text}, {"id_vendedor", type text}, {"id_producto", type text},
        {"estado_cliente", type text}, {"estado_pedido", type text}, {"precio", type number},
        {"flete", type number}, {"ingreso_linea", type number}, {"peso_flete_pct", type number},
        {"dias_entrega_real", type number}, {"dias_entrega_prometidos", Int64.Type}, {"dias_retraso", type number},
        {"llego_tarde", type number}, {"distancia_km", type number}, {"mismo_estado", type text},
        {"nota_resena", type number}, {"resena_negativa", type number}, {"resena_1_estrella", type number},
        {"metodo_pago", type text}, {"plazos", type number}, {"importe_pagado", type number},
        {"hora_compra", Int64.Type}, {"franja_horaria", type text}, {"fecha", type date}
    })
in
    t
```

`llego_tarde`, `resena_negativa` y `resena_1_estrella` se cargan como número y no como entero a propósito: valen 0 o 1, y así su media en DAX devuelve directamente la proporción.

#### `dim_fecha`

```m
let
    t = LeerCsv("modelo_estrella\dim_fecha.csv.gz", {
        {"fecha", type date}, {"anio", Int64.Type}, {"mes", Int64.Type},
        {"nombre_mes", type text}, {"trimestre", Int64.Type}, {"dia_semana", type text},
        {"es_fin_de_semana", type logical}, {"anio_mes", type text}
    })
in
    t
```

#### `dim_cliente`

```m
let
    t = LeerCsv("modelo_estrella\dim_cliente.csv.gz", {
        {"id_cliente_unico", type text}, {"ciudad_cliente", type text}, {"estado_cliente", type text},
        {"cliente_lat", type number}, {"cliente_lng", type number}
    })
in
    t
```

#### `dim_vendedor`

```m
let
    t = LeerCsv("modelo_estrella\dim_vendedor.csv.gz", {
        {"id_vendedor", type text}, {"ciudad_vendedor", type text}, {"estado_vendedor", type text},
        {"region_vendedor", type text}, {"vendedor_lat", type number}, {"vendedor_lng", type number}
    })
in
    t
```

#### `dim_producto`

```m
let
    t = LeerCsv("modelo_estrella\dim_producto.csv.gz", {
        {"id_producto", type text}, {"categoria", type text}, {"peso_g", type number},
        {"largo_cm", type number}, {"alto_cm", type number}, {"ancho_cm", type number},
        {"volumen_cm3", type number}, {"num_fotos", type number}
    })
in
    t
```

#### `dim_estado`

```m
let
    t = LeerCsv("modelo_estrella\dim_estado.csv.gz", {
        {"estado", type text}, {"estado_nombre", type text}, {"region", type text},
        {"poblacion", Int64.Type}, {"pib_per_capita", type number}, {"tasa_pobreza", type number},
        {"densidad", type number}, {"idh", type number}, {"estado_lat", type number},
        {"estado_lng", type number}
    })
in
    t
```

#### `v_impacto_retraso`

```m
let
    t = LeerCsv("vistas\v_impacto_retraso.csv", {
        {"tramo_retraso", type text}, {"pedidos", Int64.Type}, {"nota_media", type number},
        {"pct_una_estrella", type number}, {"pct_negativas", type number}, {"facturacion", type number}
    })
in
    t
```

#### `v_rendimiento_vendedores`

```m
let
    t = LeerCsv("vistas\v_rendimiento_vendedores.csv", {
        {"id_vendedor", type text}, {"ciudad_vendedor", type text}, {"estado_vendedor", type text},
        {"region_vendedor", type text}, {"vendedor_lat", type number}, {"vendedor_lng", type number},
        {"pedidos", Int64.Type}, {"facturacion", type number}, {"nota_media", type number},
        {"pct_entregas_tardias", type number}, {"pct_una_estrella", type number}, {"dias_entrega", type number},
        {"semaforo", type text}, {"cuartil_facturacion", Int64.Type}
    })
in
    t
```

#### `v_ventas_por_estado`

```m
let
    t = LeerCsv("vistas\v_ventas_por_estado.csv", {
        {"estado", type text}, {"estado_nombre", type text}, {"region", type text},
        {"poblacion", Int64.Type}, {"pib_per_capita", type number}, {"idh", type number},
        {"tasa_pobreza", type number}, {"estado_lat", type number}, {"estado_lng", type number},
        {"pedidos", Int64.Type}, {"clientes", Int64.Type}, {"facturacion", type number},
        {"gasto_por_habitante", type number}, {"clientes_por_10k_hab", type number}, {"nota_media", type number},
        {"pct_entregas_tardias", type number}, {"dias_entrega", type number}, {"distancia_media_km", type number},
        {"peso_flete_pct", type number}, {"puesto_facturacion", Int64.Type}, {"puesto_penetracion", Int64.Type}
    })
in
    t
```

#### `v_categorias`

```m
let
    t = LeerCsv("vistas\v_categorias.csv", {
        {"categoria", type text}, {"lineas", Int64.Type}, {"pedidos", Int64.Type},
        {"facturacion", type number}, {"precio_medio", type number}, {"peso_flete_pct", type number},
        {"peso_medio_kg", type number}, {"nota_media", type number}, {"pct_entregas_tardias", type number},
        {"cuota_facturacion_pct", type number}
    })
in
    t
```

#### `v_evolucion_mensual`

```m
let
    t = LeerCsv("vistas\v_evolucion_mensual.csv", {
        {"anio_mes", type text}, {"primer_dia", type date}, {"pedidos", Int64.Type},
        {"facturacion", type number}, {"nota_media", type number}, {"facturacion_media_movil_3m", type number},
        {"variacion_mensual_pct", type number}, {"pct_entregas_tardias", type number}
    })
in
    t
```

### 1.4 Cerrar y comprobar

**Inicio → Cerrar y aplicar.** Tarda un par de minutos: `hechos_ventas` son 112.650 filas y `dim_cliente` 95.420.

Comprueba de inmediato que la carga ha ido bien, antes de seguir. En una tabla cualquiera del lienzo, pon `hechos_ventas[ingreso_linea]` con agregación Suma: debe dar **15.843.553,24**. Si sale un número desorbitado, los decimales se han leído como miles y hay que revisar que el `"en-US"` esté en la función `LeerCsv`.

---

## 2. El modelo de datos

En la pestaña **Modelo**, Power BI habrá detectado algunas relaciones por su cuenta. Estas cinco son las que deben existir, todas **Varios a uno** y de dirección **Simple**:

| Desde | Hacia |
|---|---|
| `hechos_ventas[fecha]` | `dim_fecha[fecha]` |
| `hechos_ventas[id_cliente_unico]` | `dim_cliente[id_cliente_unico]` |
| `hechos_ventas[id_vendedor]` | `dim_vendedor[id_vendedor]` |
| `hechos_ventas[id_producto]` | `dim_producto[id_producto]` |
| `hechos_ventas[estado_cliente]` | `dim_estado[estado]` |

Las claves están verificadas: las cinco dimensiones son únicas, sin nulos, y no hay ni una sola fila de hechos huérfana. Las relaciones entran sin avisos.

Las cinco tablas `v_*` se quedan **sin relacionar**. Cada una alimenta sus propios visuales con su propio grano, y relacionarlas introduciría ambigüedad en el modelo.

**Marcar la tabla de calendario.** Selecciona `dim_fecha` → **Herramientas de tabla → Marcar como tabla de fechas** → columna `fecha`. Sin esto, `SAMEPERIODLASTYEAR` y `DATESYTD` no funcionan.

**Ocultar el ruido.** Clic derecho → *Ocultar en la vista de informe* sobre los identificadores (`id_pedido`, `id_cliente_unico`, `id_vendedor`, `id_producto`) y sobre `dim_fecha[nombre_mes]` y `dim_fecha[dia_semana]`, que vienen en inglés del origen y no se usan en ningún visual. El panel de campos queda limpio y nadie construye nada por error sobre una columna que no toca.

---

## 3. Medidas DAX

Crea una tabla para agruparlas: **Inicio → Especificar datos**, nómbrala `_Medidas`, acepta con la columna vacía y luego borra esa columna desde Power Query. Después, con `_Medidas` seleccionada, **Nueva medida** para cada bloque.

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

`llego_tarde` vale 1 o 0, así que su media es la proporción directamente. Formatéala como porcentaje con un decimal.

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

```dax
Estados cubiertos = DISTINCTCOUNT(v_ventas_por_estado[estado])
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

Se usa en **Formato → Color de fuente → fx → Formato por: Valor del campo**, eligiendo esta medida.

### Formatos de número

Con cada medida seleccionada, en **Herramientas de medición**:

| Medidas | Formato |
|---|---|
| Facturación, Facturación producto, Facturación flete, Facturación en riesgo | Número entero, separador de miles |
| Ticket medio, Gasto por habitante | Dos decimales |
| Pedidos, Clientes, Vendedores activos, Vendedores críticos, Estados cubiertos | Número entero |
| % Entregas tardías, % de 1 estrella, % negativas, Peso del flete %, Variación interanual % | Porcentaje, un decimal |
| Nota media y derivadas, Días de entrega, Distancia media | Dos decimales |

---

## 4. El tema

**Vista → Temas → Buscar temas** y selecciona `powerbi/tema_olist.json`.

Deja resueltos de una vez los colores, la tipografía, el fondo de página, la cuadrícula tenue, las esquinas redondeadas y la desaparición de bordes y sombras. Todo lo que añadas después lo hereda, así que es el primer paso antes de colocar un solo visual.

La paleta está comprobada para que las series sigan distinguiéndose con daltonismo:

| Uso | Color |
|---|---|
| Serie principal | `#2a78d6` |
| Contraste / alerta | `#eb6834` |
| Positivo | `#1baf7a` |
| Aviso | `#eda100` |
| Crítico | `#e34948` |

Tres reglas que el tema no puede imponer por ti:

- **Un solo eje por gráfico.** Nada de doble eje vertical: si hay dos medidas de escalas distintas, se hacen dos gráficos.
- **Nunca cuadrícula vertical y horizontal a la vez.** El tema ya deja solo la horizontal.
- **Títulos que digan algo.** «Llegar tarde hunde la valoración» comunica mucho más que «Nota media por tramo de retraso». Los títulos de abajo están escritos así a propósito.

---

## 5. Las tres páginas

El lienzo es el estándar **16:9, 1280 × 720**. Para cada visual, selecciónalo y escribe su posición y tamaño en **Formato → General → Propiedades → Posición**. Teclear estos cuatro números por visual es lo que separa un informe que parece diseñado de uno que parece colocado a ojo.

### Página 1 · Visión general

Para dirección: cómo va el negocio.

| Visual | Tipo | Campos | X | Y | An. | Al. |
|---|---|---|---|---|---|---|
| Título «Olist · Visión general del negocio» | Cuadro de texto | — | 24 | 16 | 600 | 36 |
| Año | Segmentación (desplegable) | `dim_fecha[anio]` | 716 | 20 | 176 | 36 |
| Región | Segmentación (desplegable) | `dim_estado[region]` | 900 | 20 | 176 | 36 |
| Categoría | Segmentación (desplegable) | `dim_producto[categoria]` | 1084 | 20 | 176 | 36 |
| Facturación | Tarjeta | `[Facturación]` | 24 | 72 | 232 | 92 |
| Pedidos | Tarjeta | `[Pedidos]` | 274 | 72 | 232 | 92 |
| Clientes | Tarjeta | `[Clientes]` | 524 | 72 | 232 | 92 |
| Nota media | Tarjeta | `[Nota media]` | 774 | 72 | 232 | 92 |
| Entregas tardías | Tarjeta | `[% Entregas tardías]` | 1024 | 72 | 232 | 92 |
| «De 57.000 reales al mes a más de un millón en dos años» | Gráfico de áreas | Eje X `dim_fecha[anio_mes]` · Eje Y `[Facturación]` | 24 | 180 | 760 | 256 |
| «São Paulo concentra el 37% del negocio» | Mapa | Lat. `dim_estado[estado_lat]` · Long. `dim_estado[estado_lng]` · Tamaño `[Facturación]` · Leyenda `dim_estado[region]` | 808 | 180 | 448 | 256 |
| «Diez categorías concentran dos tercios de los ingresos» | Barras horizontales | Eje Y `v_categorias[categoria]` · Eje X `v_categorias[facturacion]` | 24 | 452 | 392 | 240 |
| «Más de la mitad de los pedidos recibe cinco estrellas» | Columnas | Eje X `hechos_ventas[nota_resena]` · Eje Y Recuento de `id_pedido` | 444 | 452 | 392 | 240 |
| «El sudeste acorta el plazo a la mitad» | Barras horizontales | Eje Y `dim_estado[region]` · Eje X `[Días de entrega]` | 864 | 452 | 392 | 240 |

Detalles que importan:

- En el gráfico de áreas, **Analítica → Línea de tendencia** activada.
- En las barras de categorías, **Filtros del visual → Filtrado N superior = 10** por `facturacion`.
- En la distribución de notas, colorea de `#e34948` las columnas 1 y 2 y deja el resto en azul: la mirada va directa al problema.
- Las tres segmentaciones en modo **Desplegable** (Formato → Configuración de segmentación → Estilo), para que no se coman la página.

### Página 2 · Calidad del servicio

Para operaciones: dónde está el problema. Es la página del hallazgo central.

| Visual | Tipo | Campos | X | Y | An. | Al. |
|---|---|---|---|---|---|---|
| Título «Calidad del servicio · el coste de llegar tarde» | Cuadro de texto | — | 24 | 16 | 700 | 36 |
| Entregas tardías | Tarjeta | `[% Entregas tardías]` | 24 | 72 | 294 | 92 |
| Días de entrega | Tarjeta | `[Días de entrega]` | 336 | 72 | 294 | 92 |
| Nota si llega a tiempo | Tarjeta | `[Nota si llega a tiempo]` | 648 | 72 | 294 | 92 |
| Nota si llega tarde | Tarjeta | `[Nota si llega tarde]` | 960 | 72 | 294 | 92 |
| «La nota cae en escalera según crece el retraso» | Columnas | Eje X `v_impacto_retraso[tramo_retraso]` · Eje Y `v_impacto_retraso[nota_media]` | 24 | 180 | 604 | 256 |
| «Pasada una semana, siete de cada diez dan una estrella» | Columnas | Eje X `v_impacto_retraso[tramo_retraso]` · Eje Y `v_impacto_retraso[pct_una_estrella]` | 652 | 180 | 604 | 256 |
| «Veinte vendedores concentran el problema» | Dispersión | Eje X `pct_entregas_tardias` · Eje Y `nota_media` · Tamaño `facturacion` · Leyenda `semaforo` · Detalles `id_vendedor` | 24 | 452 | 604 | 240 |
| Vendedores críticos | Tabla | `id_vendedor`, `estado_vendedor`, `pedidos`, `facturacion`, `pct_entregas_tardias`, `nota_media` | 652 | 452 | 604 | 240 |

Detalles que importan:

- Las dos tarjetas de nota, **una al lado de la otra, cuentan la historia entera**: 4,21 frente a 2,26. No hace falta ningún texto explicativo.
- En los dos gráficos de tramos, colorea de azul los tres primeros tramos (entregas adelantadas) y de naranja `#eb6834` los cuatro últimos (entregas tardías). El salto de color cae justo donde cae el escalón de la nota.
- En la dispersión, fija los colores de la leyenda: Correcto `#1baf7a`, Vigilar `#eda100`, Crítico `#e34948`.
- En la tabla, **Filtros del visual → `semaforo` es «Crítico»**, y ordénala por `facturacion` descendente. Aplica el formato condicional del semáforo sobre la columna de porcentaje.

### Página 3 · Oportunidad comercial

Para el equipo comercial: dónde crecer.

| Visual | Tipo | Campos | X | Y | An. | Al. |
|---|---|---|---|---|---|---|
| Título «Oportunidad comercial · dónde queda recorrido» | Cuadro de texto | — | 24 | 16 | 700 | 36 |
| Gasto por habitante | Tarjeta | `[Gasto por habitante]` | 24 | 72 | 398 | 92 |
| Clientes por 10.000 hab. | Tarjeta | `[Clientes por 10.000 habitantes]` | 440 | 72 | 398 | 92 |
| Estados cubiertos | Tarjeta | `[Estados cubiertos]` | 856 | 72 | 398 | 92 |
| «El desarrollo del estado explica el gasto, pero no en todos» | Dispersión | Eje X `v_ventas_por_estado[idh]` · Eje Y `gasto_por_habitante` · Tamaño `poblacion` · Detalles `estado` | 24 | 180 | 760 | 256 |
| «La penetración se concentra en el sudeste» | Mapa | Lat. `estado_lat` · Long. `estado_lng` · Tamaño `gasto_por_habitante` · Leyenda `region` | 808 | 180 | 448 | 256 |
| Estados ordenados por recorrido | Tabla | `estado_nombre`, `facturacion`, `gasto_por_habitante`, `puesto_penetracion`, `pct_entregas_tardias`, `dias_entrega` | 24 | 452 | 760 | 240 |
| «Los estados del norte esperan el triple» | Barras horizontales | Eje Y `v_ventas_por_estado[estado]` · Eje X `dias_entrega` | 808 | 452 | 448 | 240 |

Detalles que importan:

- En la dispersión, **Analítica → Línea de tendencia** activada: los estados por debajo de la recta son exactamente la oportunidad comercial, y se ven de un golpe de vista.
- En la tabla, ordena por `puesto_penetracion` ascendente.
- En las barras de días de entrega, ordena de mayor a menor y deja solo los diez primeros con **Filtrado N superior**.
- Esta página y la anterior se cierran entre sí, y conviene decirlo en la conclusión: la correlación entre el gasto por habitante de un estado y su plazo de entrega es de **−0,84**. Roraima y Amapá esperan 27,8 días frente a los 8,3 de São Paulo, y son justo los estados donde menos se vende. El plazo no es solo un problema de atención al cliente: es la barrera de entrada a los mercados que quedan por abrir.

### Navegación

**Insertar → Botones → Navegador de páginas** en la página 1, y cópialo con Ctrl+C / Ctrl+V en las otras dos para que quede en la misma posición. Colócalo en X 24, Y 700 si lo quieres como pie, o déjalo arriba a la derecha.

---

## 6. Antes de dar por cerrado el informe

**Cuadra los totales.** Con todos los filtros limpios, la página 1 debe mostrar:

| Indicador | Valor |
|---|---|
| Facturación | 15.843.553 R$ |
| Pedidos | 98.666 |
| Clientes | 95.420 |
| Nota media | 4,03 |
| Entregas tardías | 6,6 % |

Si alguno no cuadra, el problema está en una relación del modelo o en un filtro que se ha quedado puesto, no en los datos.

**Prueba los filtros.** Selecciona un año en la página 1 y comprueba que las tarjetas y los tres gráficos responden. Las páginas 2 y 3 se alimentan de las vistas, que no están relacionadas con el calendario, así que no deben moverse: es el comportamiento esperado.

**Guarda el archivo** como `powerbi/dashboard_olist.pbix`, dentro del repositorio.

**Captura las tres páginas.** Con cada página abierta, Win+Mayús+S para recortar el lienzo completo, y guarda en `powerbi/capturas/` como `pagina_1_vision_general.png`, `pagina_2_calidad_servicio.png` y `pagina_3_oportunidad_comercial.png`. Exporta además el informe entero a PDF desde **Archivo → Exportar → PDF** y guárdalo como `powerbi/dashboard_olist.pdf`: así quien no tenga Power BI instalado también puede verlo.

---

## Anexo · La alternativa con PostgreSQL

El modelo también se puede alimentar desde la base de datos, que es de donde salen las vistas materializadas. Si se prefiere esa ruta:

1. Ejecutar `sql/01_esquema.sql` para crear el modelo en estrella.
2. Cargar los datos. `sql/02_cargar_datos.py` lo hace desde Python; también vale `\copy` desde psql, descomprimiendo antes los `.csv.gz`.
3. Ejecutar `sql/03_vistas_analiticas.sql` para crear las seis vistas.
4. En Power BI, **Obtener datos → Base de datos → PostgreSQL**, servidor `localhost`, base de datos `olist`, modo **Importar**. La primera vez pedirá instalar el conector **Npgsql**.
5. Marcar las seis tablas del modelo en estrella y las vistas `v_ventas_por_estado`, `v_rendimiento_vendedores`, `v_categorias`, `v_impacto_retraso` y `v_evolucion_mensual`.

Los nombres de tabla, columna y las medidas DAX son idénticos, así que el resto de la guía se sigue igual sin cambiar una sola línea. La ruta de Power Query es la que está documentada como principal por un motivo práctico: no obliga a tener el servidor levantado para abrir el informe.
