# Guía de ejecución

## Instalación

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Diagnóstico

```powershell
mvi doctor
```

## Análisis DSP

```powershell
mvi analyze "C:\ruta\cancion.mp3"
```

Con portada:

```powershell
mvi analyze "C:\ruta\cancion.mp3" --cover "C:\ruta\portada.jpg"
```

Con exportación CSV:

```powershell
mvi analyze "C:\ruta\cancion.mp3" --csv data\cancion.csv
```

## Pruebas

```powershell
pytest
```

## Reconocimiento automático

> **Nota de plataforma:** `mvi setup-fpcalc` descarga actualmente el binario
> oficial de Chromaprint **solo para Windows x86_64**. En Linux/macOS,
> instala `fpcalc` por tu cuenta (por ejemplo, vía el gestor de paquetes de
> tu sistema o los binarios oficiales de Chromaprint) y expón su ruta con
> la variable de entorno `MVI_FPCALC`, o asegúrate de que esté en el PATH.
> El resto del pipeline de reconocimiento (AcoustID, MusicBrainz, Cover Art
> Archive) es multiplataforma.

Configurar la clave de AcoustID solo mediante variable de entorno:

```powershell
$env:MVI_ACOUSTID_CLIENT="TU_CLIENT_KEY"
```

Descargar `fpcalc` dentro del propio proyecto (Windows):

```powershell
mvi setup-fpcalc
```

Verificar:

```powershell
mvi doctor
```

Reconocer:

```powershell
mvi identify "C:\ruta\cancion.mp3"
```

La identidad se guarda en:

```text
cache/identity/
```

## Diseños

```powershell
mvi designs list
```

# Music Visual Intelligence — V1.2

## Estado

Núcleo local de análisis + reconocimiento + diseño automático de portada.

Esta versión está diseñada específicamente para funcionar con **Python 3.14** sin depender de `librosa` ni `scipy`.

La prioridad actual es:

```text
correctitud técnica
+
modularidad
+
persistencia
+
rendimiento medible
```

antes de incorporar GUI, separación de instrumentos o visualización en tiempo real.

---

## Dependencias

```text
Python >= 3.14
NumPy
SoundFile
Pillow
psutil
```

No se requiere:

```text
librosa
scipy
numba
scikit-learn
```

Esto reduce la superficie de dependencias binarias y evita que SciPy sea necesario para ejecutar el núcleo.

---

## Generar una señal controlada

Para probar el pipeline sin usar una canción comercial:

```powershell
python tools\generate_test_tone.py
```

Después:

```powershell
mvi analyze data\test_signal.wav
```

La señal está construida deliberadamente con:

```text
0–3 s    100 Hz
3–6 s    440 Hz
6–9 s    2000 Hz
9–12 s   100 Hz + 2000 Hz
```

Esto permite comprobar que los cambios espectrales aparecen donde esperamos.
La suite de tests incluye un test de integración (`tests/test_integration_pipeline.py`)
que corre el pipeline completo sobre esta misma señal y valida que la
detección de bandas y de eventos de cambio se comporte razonablemente
contra ese ground truth conocido.

> Nota: con un tono puro de baja frecuencia (100 Hz), el propio STFT genera
> cierto ruido de fuga espectral que puede opacar la detección de algún
> límite puntual. Es un comportamiento esperado del método V1 de novelty
> por spectral flux, no un fallo del pipeline; con contenido de banda
> ancha (música real) el detector se comporta de forma más estable.

---

## Analizar una canción real

```powershell
mvi analyze "C:\ruta\cancion.mp3"
```

Con portada:

```powershell
mvi analyze "C:\ruta\cancion.mp3" --cover "C:\ruta\portada.jpg"
```

Guardar JSON:

```powershell
mvi analyze "C:\ruta\cancion.mp3" --output data\cancion.json
```

Guardar además CSV:

```powershell
mvi analyze "C:\ruta\cancion.mp3" --output data\cancion.json --csv data\cancion_timeline.csv
```

---

# Arquitectura

```text
                  AUDIO FILE
                       |
                       v
                SoundFile decoder
                       |
                       v
                  NumPy mono
                       |
                       v
               Optional resampling
                       |
                       v
                 NumPy STFT
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
     Spectral        Temporal       Rhythm
     Features        Features       Features
        |              |              |
        +--------------+--------------+
                       |
                       v
                Canonical Timeline
                       |
            +----------+----------+
            |                     |
            v                     v
          Events               Segments
            |                     |
            +----------+----------+
                       |
                       v
                JSON / Cache
                       |
              +--------+--------+
              |                 |
              v                 v
        Automatic Design   Personal Designs
```

---

# Modelo temporal

La STFT se calcula con:

```text
sample rate = 44100 Hz
FFT size    = 2048
hop         = 512
window      = Hann
```

La resolución interna aproximada es:

```text
44100 / 512 = 86.13 frames/s
```

La representación persistente se reduce a:

```text
10 frames/s
```

La reducción no consiste en descartar simplemente frames.

Cada bloque utiliza una estrategia específica:

| Variable | Agregación |
|---|---|
| Energy | media |
| Bass/Mids/Highs | media |
| Brightness | media |
| Novelty | máximo |
| Onset strength | máximo |
| Rhythm | media |
| Salience | máximo |

Esto permite conservar eventos fuertes aunque el almacenamiento final sea mucho menor que la resolución interna.

---

# Componentes V1

Cada frame contiene:

```text
bass_db
mids_db
highs_db

rms
rms_db

spectral_centroid_hz
brightness

onset_strength
novelty
rhythm
context_contrast
spectral_contrast

salience
```

---

# DSP

## STFT

La STFT se implementa directamente usando ventanas Hann, `sliding_window_view` y `numpy.fft.rfft`.

```text
audio
  ↓
frames
  ↓
Hann window
  ↓
rFFT
  ↓
magnitude spectrum
```

No se usa SciPy.

---

## RMS

```math
RMS = sqrt(mean(x²))
```

La representación logarítmica:

```math
RMS_dB = 20 log10(RMS + ε)
```

---

## Bandas

```text
Bass  = 20–250 Hz
Mids  = 250–2000 Hz
Highs = 2000–12000 Hz
```

Estas bandas son descriptores funcionales para el sistema visual.

No deben interpretarse como una descomposición psicoacústica completa.

---

## Centroide espectral

```math
C = Σ(f_k M_k) / ΣM_k
```

Se convierte posteriormente en:

```text
brightness ∈ [0, 1]
```

mediante normalización relativa por canción.

---

## Flux / Novelty

V1 utiliza un flujo espectral basado en cambios positivos de la magnitud logarítmica:

```math
Δ_k,t = max(0, log(1 + M_k,t) - log(1 + M_k,t-1))
```

y:

```math
Flux_t = sqrt(Σ Δ_k,t²)
```

Después se normaliza (percentil 5–95, recortado a [0,1]) para formar la serie de `novelty`.

---

# Tempo y beats

La estimación V1 es deliberadamente ligera.

Se calcula:

```text
onset/flux
   ↓
autocorrelación
   ↓
periodo dominante
   ↓
BPM estimado
```

Después se generan candidatos de beat alrededor de esa periodicidad y se ajustan hacia los máximos locales de actividad.

Esto **no pretende competir todavía con un beat tracker avanzado de MIR**.

Su función V1 es:

```text
tener una referencia rítmica reproducible
+
proporcionar eventos temporales
+
alimentar la visualización
```

Una implementación MIR más sofisticada podrá sustituirse posteriormente detrás de la misma interfaz.

---

# Detección de cambios (eventos)

Un frame se marca como cambio significativo cuando su `novelty` cae dentro
del extremo superior de la distribución de la propia canción. El parámetro
`significant_change_z` en `config.py` se interpreta como un z-score
equivalente bajo una normal (por ejemplo, `2.0` ≈ percentil 97.7), pero el
umbral real se calcula directamente sobre el percentil de la muestra, no
sobre media/desviación estándar paramétrica.

Esto es intencional: `novelty` ya viene recortada a `[0, 1]` por
`percentile_normalize`, lo cual satura varios frames exactamente en `1.0`.
Sobre una distribución así, un z-score paramétrico rara vez alcanza `2.0`
aunque existan picos reales evidentes, así que un umbral basado en
percentil de la muestra es más robusto sin asumir una distribución normal.

---

# Salience

La saliencia sigue siendo una interpretación del sistema.

```math
S = sigmoid(
    w_E E
  + w_N N
  + w_R R
  + w_C C
  + w_X X
  - b
)
```

donde:

```text
E = energy
N = novelty
R = rhythm
C = spectral contrast
X = context contrast
```

Los pesos están en:

```text
music_visual_intelligence/config.py
```

No deben interpretarse como constantes universales de percepción humana.

---

# Caché

La caché ahora se consulta **antes de ejecutar el DSP**.

```text
file
 ↓
SHA-256
 ↓
analysis version
 ↓
cache lookup
```

Si encontramos:

```text
<fingerprint>_canonical-v1.json
```

el pipeline carga el resultado.

Por tanto:

```text
first run:
hash → DSP → save

second run:
hash → load
```

La segunda ejecución no necesita volver a calcular la STFT, flux, tempo, beats o segmentos.

Todas las escrituras de caché (análisis, identidad, diseños) son **atómicas**:
se escribe a un archivo temporal en el mismo directorio y se reemplaza con
`os.replace`, para que una interrupción a mitad de escritura nunca deje un
JSON corrupto o truncado.

La deserialización de JSON hacia dataclasses (análisis, identidad, diseños)
ignora campos desconocidos, para que un esquema futuro con campos nuevos
siga siendo legible por versiones anteriores del código.

---

# Diseños

La arquitectura ya separa:

```text
Canonical Analysis
        |
        +------ Automatic Design
        |
        +------ Personal Design A
        |
        +------ Personal Design B
        |
        +------ Personal Design C
```

## Automatic Design

Se genera desde la portada.

Inicialmente:

```text
Bass → color 1
Mids → color 2
Highs → color 3
```

La lógica se volverá más sofisticada posteriormente.

---

## Personal Design

Un diseño personal almacena solo modificaciones:

```text
design_id
name
base_analysis_fingerprint

component_colors
multipliers
transition_smoothing
beat_pulse_enabled
beat_pulse_strength
segment_labels
notes
```

Esto evita duplicar el análisis musical.

---

# Listar diseños

```powershell
mvi designs list
```

Filtrar por canción:

```powershell
mvi designs list <fingerprint>
```

La biblioteca queda almacenada en:

```text
cache/designs/
├── automatic/
└── personal/
```

---

# Exportación CSV

El timeline puede exportarse:

```powershell
mvi analyze song.wav --csv data/song_timeline.csv
```

Esto permitirá abrir los datos en:

- Excel;
- Python;
- MATLAB;
- R;
- herramientas de visualización;
- notebooks.

El CSV representa la capa temporal persistente, no el espectro completo.

---

# Rendimiento

La salida informa:

```text
decode_seconds
feature_extraction_seconds
beat_detection_seconds
temporal_model_seconds
fingerprint_seconds
total_seconds
real_time_factor
audio_seconds_per_processing_second
peak_rss_mb
```

## RTF

```math
RTF = processing_time / audio_duration
```

Objetivo:

```text
RTF < 1
```

## Throughput

```math
throughput =
audio_seconds / processing_seconds
```

Un valor de:

```text
20
```

significa:

```text
20 segundos de audio procesados por cada segundo real.
```

Este número debe considerarse dependiente del hardware y de la configuración.

---

# Pruebas

Ejecutar:

```powershell
pytest
```

La suite incluye:

- agregación temporal;
- detección de flux;
- estimación de tempo;
- detección de eventos de cambio (incluyendo un caso de regresión sobre
  distribuciones recortadas en el techo);
- serialización/deserialización de caché (incluida tolerancia a esquemas
  futuros con campos desconocidos);
- persistencia de diseños (incluida verificación de que las escrituras
  atómicas no dejan archivos temporales sueltos);
- reconocimiento (helpers de AcoustID/MusicBrainz, caché de identidad);
- **un test de integración end-to-end** que corre el pipeline completo
  sobre la señal sintética de `tools/generate_test_tone.py` y valida
  duración, bandas dominantes por tramo, eventos de cambio y segmentos
  contra el ground truth conocido de la señal.

---

# Reconocimiento musical

El flujo es:

```text
Audio
 ↓
Chromaprint / fpcalc
 ↓
AcoustID
 ↓
MusicBrainz Recording
 ↓
Release / Release Group
 ↓
Cover Art URL
```

AcoustID requiere una clave `client`, limita su Web Service a 3 solicitudes
por segundo y declara el uso gratuito como no comercial.

Chromaprint publica oficialmente `fpcalc`. El comando `mvi setup-fpcalc`
descarga ese binario dentro del proyecto (actualmente solo para Windows
x86_64) y no modifica el PATH del sistema.

MusicBrainz no requiere una API key para el Web Service normal, pero exige
un `User-Agent` significativo y aproximadamente una solicitud por segundo;
el cliente MVI utiliza un intervalo mínimo de 1.1 segundos.

MusicBrainz permite solicitar releases y release-groups relacionados desde
un Recording usando `inc=`.

## Dependencias del reconocimiento

El núcleo DSP sigue funcionando sin:

```text
librosa
scipy
internet
AcoustID
fpcalc
```

El reconocimiento es un módulo independiente.

Si no está listo:

```text
mvi analyze
```

continúa funcionando.

Si se desea reconocimiento:

```text
mvi doctor
→ setup-fpcalc (Windows) o instalar fpcalc manualmente (Linux/macOS)
→ configurar MVI_ACOUSTID_CLIENT
→ mvi identify
```

## Consideraciones legales

No guardar claves API en Git.

No desactivar Windows Defender, AppLocker o Application Control.

AcoustID debe utilizarse respetando sus condiciones, especialmente la
restricción de uso no comercial del servicio gratuito.

MusicBrainz debe utilizarse respetando sus reglas de rate limiting y
User-Agent.

---

# Roadmap inmediato

## V1.2 — Actual

- [x] NumPy DSP sin SciPy/librosa
- [x] Reconocimiento (AcoustID + MusicBrainz + Cover Art Archive)
- [x] Caché de análisis e identidad, con deserialización tolerante a esquema
- [x] Escrituras de caché atómicas
- [x] Detección de eventos de cambio basada en percentil de muestra
- [x] Test de integración end-to-end contra señal sintética conocida
- [x] Diseño automático + diseños personales
- [x] Métricas de rendimiento

## V1.3 — siguiente

```text
Editor de diseño personal vía configuración
+
Caché de metadatos MusicBrainz (evitar relookups en procesamiento por lotes)
+
Soporte fpcalc en Linux/macOS
```

## V1.4

```text
Bar visualization
+
Circular visualization
```

## Futuro

```text
Microphone
Source separation
Advanced MIR
2D map
3D rendering
Physical lighting
```

---

# Principio central

La aplicación debe cumplir:

```text
ANALYZE ONCE
      ↓
STORE
      ↓
REUSE
      ↓
INTERPRET MANY TIMES
```

El audio se analiza una vez.

El análisis canónico se conserva.

Los diseños visuales pueden cambiar sin volver a ejecutar el DSP.
