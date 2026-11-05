# Radar de Tendencias — Fase 1

Detecta videos virales recientes (≤ 90 días) publicados por canales pequeños (1.000–100.000 suscriptores) que ya tienen una fórmula probada (≥ 3 videos virales), por **nicho, sub-nicho, idioma, país y formato** (largo / Shorts). Consulta la YouTube Data API v3 de forma no personalizada (sin cuenta, sin cookies).

```
config/nichos.json     catálogo de 10 nichos → sub-nichos → semillas de búsqueda (ES / EN)
config/perfiles.json   perfiles de canal: qué investiga el radar para cada canal
radar.py               rastreador (usa la API y escribe data/*.json)
index.html             página de ranking (GitHub Pages) con filtros
data/                  resultados (generados por el rastreador)
.github/workflows/     ejecución automática todas las noches
tests/fake_api.py      API simulada para probar sin red:  python radar.py --dry-run
```

## Puesta en marcha (una sola vez, ~10 min)

1. **Crear el repositorio en GitHub** (privado o público; la página de ranking requiere repositorio público si la cuenta es gratuita). Subir todos estos archivos.
2. **Guardar la clave de la API como secreto:** Settings → Secrets and variables → Actions → *New repository secret* → nombre `YOUTUBE_API_KEY`, valor `AIza…`. Nunca la pegues en el código.
3. **Activar GitHub Pages:** Settings → Pages → Source: *Deploy from a branch* → Branch `main`, carpeta `/ (root)` → Save. La página quedará en `https://<usuario>.github.io/<repo>/`.
4. **Primera ejecución manual:** pestaña *Actions* → *Radar nocturno* → *Run workflow*. Tarda 1–3 minutos; al terminar aparece un commit "radar: datos AAAA-MM-DD" y la página muestra los resultados.
5. A partir de ahí corre solo cada noche a las 03:17 (hora de Bogotá).

## Ejecutar en un computador

```bash
pip install -r requirements.txt
echo "YOUTUBE_API_KEY=AIza..." > .env
python radar.py                 # todos los perfiles
python radar.py mitribu_es      # un perfil
python -m http.server 8000      # abrir http://localhost:8000
```

## Cómo decide qué es "viral"

Para cada video: `ratio = vistas / suscriptores del canal` y `outlier = vistas / mediana de los últimos 25 videos del canal`.
Un video es viral si `ratio ≥ ratio_viral` del perfil (5× largos, 20× Shorts) **y** `outlier ≥ 3`.
Un canal entra al ranking solo si tiene ≥ `min_virales_canal` (3) videos virales entre sus últimos 25: separa la suerte de la fórmula.
`score = ratio × log10(1 + vistas por día)` prioriza lo que está creciendo ahora.

## Cuota

10.000 unidades/día gratis. Cada búsqueda cuesta 100; analizar un canal ~2. Con los 4 perfiles actuales se usan ~5.500/día.
Las semillas rotan cada día para cubrir todo el nicho a lo largo de la semana; los canales ya analizados se guardan 7 días en `data/cache_canales.json`.
Para investigar más, añade perfiles o sube `max_busquedas`, vigilando el total.

## Agregar un nicho o un canal

- Nicho nuevo: añadir una entrada en `config/nichos.json` con sub-nichos y 5–8 semillas por idioma.
- Canal nuevo: añadir un perfil en `config/perfiles.json` (copiar uno existente y cambiar nicho, idioma, formato, regiones).

## Próximas fases

2 Competencia (seguimiento diario de canales) · 3 ADN del video + guion · 4 Fábrica de Shorts · 5 Fábrica de largos y reciclaje de en vivos · 6 Tablero YPP.

## Fábrica de Shorts (Fase 4)

`fabrica/` produce un Short completo con Germancho a partir de un video viral del radar o de un tema:
ADN (transcripción + Claude) → guion en escenas → voz (ElevenLabs) → escenas con el personaje (fal.ai, referencia del libro en `assets/germancho/`) → render 1080×1920 con subtítulos (ffmpeg) → miniatura → metadatos.

Ejecutar: *Actions → Fábrica de Shorts → Run workflow* (perfil + `video_id` o `tema`). El resultado queda en `producciones/` y en la pestaña **Producciones** de la página, en estado `pendiente_aprobacion`. Secretos necesarios: `YOUTUBE_API_KEY`, `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `FAL_KEY`.
Prueba local sin APIs: `FABRICA_MOCK=1 python -m fabrica.produce --perfil mitribu_es --tema prueba`.
