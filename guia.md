1. **Imágenes Satelitales (Salud del Cultivo - NDVI):**
   - **Fuente:** [**++Microsoft Planetary Computer STAC API++**](https://planetarycomputer.microsoft.com/) (`sentinel-2-l2a`).
   - **Por qué esta y no otra:** No requiere trámites largos como Sentinel Hub. Con la librería `pystac-client` y `planetary-computer` en Python podés consultar recortes de lotes reales en Santa Fe/Córdoba, filtrar días nublados usando la banda `SCL` y calcular el índice **NDVI** (`(B08 - B04) / (B08 + B04)`).
   
      [[1](https://docs.geoanalytics.ca/2_real_world_examples/02-ndvi-s2-dask.html), [2](https://projectpythia.org/interactive-sentinel-2-cookbook/notebooks/data-intake-ms-planetary-computer/), [3](https://github.com/microsoft/PlanetaryComputer/issues/349), [4](https://docs.planet.com/guides/sentinel-2-l2a-aoi-statistics/)]
2. **Clima y Lluvias por Lote:**
   - **Fuente:** [**++Open-Meteo Archive API++**](https://open-meteo.com/).
   - **Qué extraés:** Milímetros de lluvia acumulada y estrés térmico (heladas o golpes de calor) pasando las coordenadas exactas `(lat, lon)` del centroide de cada lote.
3. **Riesgo Financiero Real del Productor:**
   - **Fuente:** [**++API Central de Deudores del BCRA v1.0++**](https://www.bcra.gob.ar/apis-banco-central/).
   - **Qué extraés:** Sin necesidad de autenticación, consultás `GET [https://bcra.gob.ar{cuit}](https://bcra.gob.ar{cuit})` y `/ChequesRechazados/{cuit}` para obtener deuda total en bancos, situación crediticia (1 a 5) y cheques sin fondos de empresas agropecuarias reales (CUITs públicos de sociedades del sector). [[1](https://www.bcra.gob.ar/apis-banco-central/), [2](https://www.bcra.gob.ar/archivos/Catalogo/Content/files/pdf/central-deudores-v1.pdf)]
4. **Precios de Granos y Tipo de Cambio:**
   - **Fuente:** API Pública de [granos.ar](http://granos.ar) (o [**++API Precios FOB MAGyP++**](https://www.magyp.gob.ar/sitio/areas/ss_mercados_agropecuarios/fob_oficiales/_archivos/000021_Precios%20Fob%20Api.php)).
   - **Qué extraés:** Precios pizarra Rosario (soja, maíz, trigo en ARS/tn y USD/tn) y cotización del dólar mayorista para valorar cuánto dinero representa la cosecha estimada de cada lote. [[1](https://granos.ar/api-docs/), [2](https://www.magyp.gob.ar/sitio/areas/ss_mercados_agropecuarios/fob_oficiales/_archivos/000021_Precios%20Fob%20Api.php)]

---

**3. Cómo conectar los datos sin inventar relaciones falsas**

Para mantener el rigor de ingeniería, armás una **tabla maestra de cartera simulada (**`dim_cartera_clientes`**)** con **50 a 200 productores/empresas agropecuarias reales de Santa Fe** (cuyos CUITs son públicos en registros comerciales) asignándoles **polígonos de lotes agrícolas reales** visibles en el mapa satelital de la zona núcleo (ej. departamentos Rosario, Caseros, Constitución, General López).

- **Cruces 100% auténticos:**
  - `Polígono del Lote (GeoJSON)` → cruza espacialmente con **Sentinel-2 (NDVI)** y **Open-Meteo (Lluvias)**.
  - `CUIT del Cliente` → cruza directamente con la **API del BCRA**.
  - `Fecha de Evaluación + Cultivo (Soja/Maíz)` → cruza con **Precios Pizarra Rosario**.

---

**4. El Producto Final (El Output que genera ROI)**

Tu pipeline produce diariamente una tabla Gold llamada `fact_agro_credit_risk` que calcula:

1. **Caída de NDVI vs. Promedio Histórico del Lote:** Si el NDVI cae más de un 20% en etapa crítica (ej. enero/febrero para soja) y la lluvia acumulada en Open-Meteo está por debajo del umbral, marcás **Alerta Agronómica Alta**.
2. **Valor Esperado de Cosecha (en USD):** `Hectáreas del Lote × Rinde Estimado Ajustado por NDVI × Precio Pizarra Rosario USD/tn`.
3. **Ratio Cobertura Deuda / Cosecha:** Compara el valor de la cosecha en pie contra la deuda bancaria reportada en el BCRA. Si la deuda supera el 70% del valor proyectado de cosecha o aparecen cheques rechazados, dispara una **Alerta de Default Preventiva** para el equipo de Riesgos.

Si querés empezar hoy mismo, decime si preferís que te arme:

++El **script en Python** para conectarte a **Planetary Computer + BCRA API** y hacer tu primera prueba de extracciónO la **estructura de carpetas y**++ `docker-compose.yml` ++(con Airflow, MinIO y PostgreSQL/PostGIS) para montar el entorno completo++  
  
**Proyecto Estrella: Scoring Crediticio Agropecuario Satelital**

- **X (Imágenes Satelitales Sentinel-2):** [**++Microsoft Planetary Computer STAC API++**](https://planetarycomputer.microsoft.com/)
- **Y (Clima y Lluvias por Lote):** [**++Open-Meteo Weather API++**](https://open-meteo.com/)
- **Z (Deudas y Cheques Rechazados por CUIT):** [**++API Central de Deudores del BCRA++**](https://www.bcra.gob.ar/apis-banco-central/)
- **C (Precios de Granos y Tipo de Cambio):** [**++ArgentinaDatos API++**](https://argentinadatos.com/) y [**++Series de Tiempo - Datos Argentina++**](https://datos.gob.ar/apis) \[[1](https://open-meteo.com/), [2](https://www.bcra.gob.ar/apis-banco-central/), [3](https://argentinadatos.com/), [4](https://datos.gob.ar/apis)\]

---