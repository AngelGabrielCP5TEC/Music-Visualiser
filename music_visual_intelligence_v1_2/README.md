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

Configurar la clave de AcoustID solo mediante variable de entorno:

```powershell
$env:MVI_ACOUSTID_CLIENT="TU_CLIENT_KEY"
```

Descargar `fpcalc` dentro del propio proyecto:

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

# Music Visual Intelligence — V1.1

## Estado

Primera implementación ampliada del núcleo local.

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

antes de incorporar reconocimiento musical externo, GUI o separación de instrumentos.

---

## V1.1: qué se añadió

Respecto al núcleo anterior:

- caché realmente reutilizable mediante deserialización;
- fingerprint antes del DSP, de modo que un cache hit evita el análisis costoso;
- exportación CSV del timeline;
- almacenamiento separado de diseños automáticos;
- modelo de diseños personales;
- comando para listar diseños;
- benchmark reproducible mediante métricas del propio análisis;
- beat estimation completamente local con NumPy;
- eliminación completa de librosa/SciPy;
- pruebas adicionales para tempo, flux, persistencia y diseños.

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

## Instalación

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Verificación:

```powershell
pytest
```

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

---

## Analizar una canción real

```powershell
mvi analyze "C:\Users\Angel\Desktop\Sound\songs\Drag_Path.mp3.mpeg"
```

Con portada:

```powershell
mvi analyze `
  "C:\Users\Angel\Desktop\Sound\songs\Drag_Path.mp3.mpeg" `
  --cover "C:\Users\Angel\Desktop\Sound\cover.jpg"
```

Guardar JSON:

```powershell
mvi analyze `
  "C:\Users\Angel\Desktop\Sound\songs\Drag_Path.mp3.mpeg" `
  --output data\drag_path.json
```

Guardar además CSV:

```powershell
mvi analyze `
  "C:\Users\Angel\Desktop\Sound\songs\Drag_Path.mp3.mpeg" `
  --output data\drag_path.json `
  --csv data\drag_path_timeline.csv
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

Después se normaliza para formar la serie de `novelty`.

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

---

# Importante sobre rendimiento

El primer objetivo no es minimizar cada milisegundo.

Es construir una línea base reproducible.

Ejemplo:

```text
Audio duration = 304 s

V1.1:
processing = 7.3 s

RTF ≈ 0.024
throughput ≈ 41.6
```

Eso significa que, según esa ejecución, el análisis procesa aproximadamente 41.6 segundos de audio por segundo de cómputo.

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
- serialización/deserialización de caché;
- persistencia de diseños.

---

# Próximo módulo: reconocimiento

El siguiente módulo lógico será:

```text
Audio
  ↓
Audio Fingerprint
  ↓
Recognition Provider
  ↓
Song Identity
```

La arquitectura debe soportar distintos proveedores.

```text
RecognitionProvider
├── AcoustID
├── AudD
└── FutureProvider
```

La integración de reconocimiento queda separada deliberadamente porque los proveedores externos tienen sus propias restricciones, claves API, límites de solicitud y condiciones de uso.

AcoustID actualmente ofrece lookup mediante fingerprints de Chromaprint y exige una `client` API key; además indica un límite de 3 solicitudes por segundo y uso no comercial gratuito para su servicio web. citeturn867808search0

Cuando implementemos ese módulo se documentarán sus credenciales y requisitos por separado, sin introducirlos dentro del núcleo DSP.

---

# Metadatos y portada

Una vez obtenido un MusicBrainz Recording ID, el proyecto podrá consultar el API de MusicBrainz. Su API REST utiliza `/ws/2/` y permite lookups de entidades mediante MBID. citeturn867808search2

La portada podrá obtenerse mediante Cover Art Archive, que permite consultar una portada frontal o thumbnails de 250, 500 y 1200 px mediante un MusicBrainz Release ID o Release Group ID. citeturn672188search0

La imagen se analizará localmente y solo se conservarán los datos visuales necesarios cuando sea posible.

---

# Decisión arquitectónica importante

La V1.1 **no intenta hacer todo todavía**.

La prioridad es mantener:

```text
Audio analysis
      |
      v
Canonical data
      |
      v
Cache
      |
      +---- Automatic design
      |
      +---- Personal design
```

Luego:

```text
Recognition
Metadata
Lyrics
Visualization
```

se conectarán a esta capa.

---

# Roadmap inmediato

## V1.1 — Actual

- [x] NumPy DSP
- [x] SoundFile
- [x] Python 3.14
- [x] STFT
- [x] RMS
- [x] bandas
- [x] centroid
- [x] novelty/flux
- [x] tempo
- [x] beats
- [x] segments
- [x] salience
- [x] cache pre-DSP
- [x] cache deserialization
- [x] CSV
- [x] automatic design store
- [x] personal design model
- [x] performance metrics

## V1.2 — siguiente

```text
Recognition
    ↓
MusicBrainz metadata
    ↓
Cover Art Archive
    ↓
Automatic song identity
```

## V1.3

```text
Automatic design refinement
+
Personal design editor via configuration
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


---

# Reconocimiento musical V1.2

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

AcoustID requiere una clave `client`, limita su Web Service a 3 solicitudes por segundo y declara el uso gratuito como no comercial. citeturn430563search1

Chromaprint publica oficialmente `fpcalc` para Windows x86_64. El comando `mvi setup-fpcalc` descarga ese binario dentro del proyecto y no modifica el PATH de Windows. citeturn806092search2

MusicBrainz no requiere una API key para el Web Service normal, pero exige un `User-Agent` significativo y aproximadamente una solicitud por segundo; el cliente MVI utiliza un intervalo mínimo de 1.1 segundos. citeturn430563search0turn430563search2

MusicBrainz permite solicitar releases y release-groups relacionados desde un Recording usando `inc=`. citeturn939905search0

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
→ setup-fpcalc
→ configurar MVI_ACOUSTID_CLIENT
→ mvi identify
```

## Consideraciones legales

No guardar claves API en Git.

No desactivar Windows Defender, AppLocker o Application Control.

AcoustID debe utilizarse respetando sus condiciones, especialmente la restricción de uso no comercial del servicio gratuito. citeturn430563search1

MusicBrainz debe utilizarse respetando sus reglas de rate limiting y User-Agent. citeturn430563search0turn430563search2
