"""
Funciones de análisis estadístico inferencial.

El proyecto no se queda en describir lo que pasó: contrasta si las diferencias
observadas son estadísticamente significativas o podrían deberse al azar.
"""

import numpy as np
import pandas as pd
from scipy import stats


def intervalo_confianza_media(muestra, confianza=0.95):
    """
    Intervalo de confianza para la media de una muestra.

    Usa la distribución t de Student en lugar de la normal porque no se conoce
    la desviación típica de la población, solo la de la muestra. Con muestras
    grandes ambas convergen, pero la t es la correcta en rigor.
    """
    datos = pd.Series(muestra).dropna()
    n = len(datos)
    media = datos.mean()
    error_tipico = stats.sem(datos)
    margen = error_tipico * stats.t.ppf((1 + confianza) / 2, df=n - 1)
    return {"n": n, "media": media, "inferior": media - margen, "superior": media + margen}


def intervalo_confianza_proporcion(exitos, total, confianza=0.95):
    """
    Intervalo de confianza para una proporción por el método de Wilson.

    Se prefiere a la aproximación normal clásica porque esta última se
    comporta mal cuando la proporción se acerca a 0 o a 1, y puede llegar a
    devolver límites imposibles como -0,02 o 1,03.
    """
    if total == 0:
        return {"proporcion": np.nan, "inferior": np.nan, "superior": np.nan, "n": 0}

    z = stats.norm.ppf((1 + confianza) / 2)
    p = exitos / total
    denominador = 1 + z**2 / total
    centro = (p + z**2 / (2 * total)) / denominador
    margen = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominador

    return {"n": total, "proporcion": p, "inferior": centro - margen, "superior": centro + margen}


def d_de_cohen(grupo_a, grupo_b):
    """
    Tamaño del efecto entre dos grupos.

    Es imprescindible acompañar con esto a cualquier contraste: con 100.000
    observaciones casi cualquier diferencia sale "significativa", incluso una
    irrelevante. La d de Cohen mide cuán grande es en realidad.
    Referencia habitual: 0,2 pequeño · 0,5 medio · 0,8 grande.
    """
    a = pd.Series(grupo_a).dropna()
    b = pd.Series(grupo_b).dropna()

    # Desviación típica combinada de ambos grupos
    varianza_combinada = (
        ((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
        / (len(a) + len(b) - 2)
    )
    return (a.mean() - b.mean()) / np.sqrt(varianza_combinada)


def comparar_dos_grupos(grupo_a, grupo_b, nombre_a="grupo A", nombre_b="grupo B",
                        alpha=0.05):
    """
    Compara dos grupos con la prueba t de Welch y con Mann-Whitney.

    Se aplican las dos a propósito. La t de Welch no exige varianzas iguales,
    pero sí supone normalidad; Mann-Whitney no supone ninguna distribución y
    compara medianas. Cuando las dos coinciden, la conclusión es sólida sin
    depender de si se cumplían los supuestos.
    """
    a = pd.Series(grupo_a).dropna()
    b = pd.Series(grupo_b).dropna()

    t_stat, p_t = stats.ttest_ind(a, b, equal_var=False)
    u_stat, p_u = stats.mannwhitneyu(a, b, alternative="two-sided")
    d = d_de_cohen(a, b)

    if abs(d) < 0.2:
        magnitud = "insignificante"
    elif abs(d) < 0.5:
        magnitud = "pequeño"
    elif abs(d) < 0.8:
        magnitud = "medio"
    else:
        magnitud = "grande"

    resultado = {
        nombre_a: {"n": len(a), "media": round(a.mean(), 3), "mediana": round(a.median(), 3)},
        nombre_b: {"n": len(b), "media": round(b.mean(), 3), "mediana": round(b.median(), 3)},
        "diferencia_de_medias": round(a.mean() - b.mean(), 3),
        "t_welch": {"estadistico": round(t_stat, 2), "p_valor": p_t},
        "mann_whitney": {"estadistico": float(u_stat), "p_valor": p_u},
        "d_de_cohen": round(d, 3),
        "magnitud_del_efecto": magnitud,
        "significativo": bool(p_t < alpha and p_u < alpha),
    }
    return resultado


def chi_cuadrado(tabla_contingencia):
    """
    Prueba de independencia entre dos variables categóricas.

    Devuelve además la V de Cramér, que normaliza el estadístico a un valor
    entre 0 y 1 para poder interpretar la fuerza de la asociación. El
    chi-cuadrado a secas crece con el tamaño de la muestra y no dice nada
    sobre la magnitud.
    """
    chi2, p, gl, esperadas = stats.chi2_contingency(tabla_contingencia)

    n = tabla_contingencia.values.sum()
    dimension_menor = min(tabla_contingencia.shape) - 1
    v_cramer = np.sqrt(chi2 / (n * dimension_menor))

    return {
        "chi2": round(chi2, 2),
        "p_valor": p,
        "grados_libertad": gl,
        "v_de_cramer": round(v_cramer, 3),
        "significativo": bool(p < 0.05),
    }


def correlacion(x, y, metodo="pearson"):
    """
    Correlación entre dos variables con su p-valor.

    'pearson' mide relación lineal y exige variables continuas;
    'spearman' trabaja sobre rangos, así que detecta relaciones monótonas
    aunque no sean lineales y aguanta mejor los valores extremos.
    """
    datos = pd.DataFrame({"x": x, "y": y}).dropna()

    if metodo == "pearson":
        coef, p = stats.pearsonr(datos["x"], datos["y"])
    else:
        coef, p = stats.spearmanr(datos["x"], datos["y"])

    return {"metodo": metodo, "n": len(datos), "coeficiente": round(coef, 4),
            "p_valor": p, "significativo": bool(p < 0.05)}


def formatear_p(p):
    """Formatea un p-valor para mostrarlo en un informe."""
    if p < 0.001:
        return "p < 0,001"
    return f"p = {p:.4f}".replace(".", ",")
