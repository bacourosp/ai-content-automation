# AI Content Automation (local, low-resource)

Automatización local para:

- Detectar nuevos posts sobre IA en X.com (vía X API).
- Decidir reutilización y ángulo viral con un LLM: **Gemini** (por defecto, gratis) o DeepSeek vía NVIDIA API.
- Generar guiones/assets por plataforma (TikTok/Instagram/Facebook).
- Renderizar video con Higgsfield vía MCP.
- Encolar y (opcionalmente) publicar con reintentos y estado persistente en SQLite.

No usa OpenClaw. La orquestación es un runtime liviano en Python con procesos cortos por etapa.

## Requisitos

- Python 3.11+

## Instalación

```bash
cd ai-content-automation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

## Configuración

Copiar el `.env` del directorio superior al directorio del proyecto o exportar variables en tu shell.

Por defecto el runtime busca `.env` en:

1) `./.env` (en el directorio actual)
2) `../.env` (un nivel arriba)
3) `/etc/xai-automation/xai.env`
4) `~/.config/xai-automation/xai.env`

También puedes forzar una ruta exacta con:

- `XAI_ENV_FILE=/ruta/a/tu.env`

Plantilla completa de variables (con comentarios y de dónde sacar cada credencial): [.env.example](.env.example).

### LLM por defecto

El proveedor por defecto es **Gemini** (`LLM_PROVIDER=gemini`, `GEMINI_MODEL=gemini-2.5-flash`) por su tier gratuito amplio y salida JSON fiable. Alternativa: `LLM_PROVIDER=nvidia` con `DEEPSEEK_MODEL=deepseek-ai/deepseek-v3.1-terminus`.

### Proveedor de render (seleccionable)

El render de video es **seleccionable** con `RENDER_PROVIDER` (default `higgsfield`) para probar cuál da mejor resultado: `higgsfield`, `mcp` (cualquier MCP de render por HTTP que controles), `glif` (oficial, vía stdio, restringido a un glif id fijo), `remotion_media` (vía stdio → kie.ai) y `remotion_app` (HTTP, **solo self-host**, ejecuta código generado por IA). Generación de imágenes para carruseles con la **API oficial de Gemini** (`ENABLE_IMAGE_GEN=true`). Detalle y notas de seguridad: [docs/SETUP_PLATFORMS.md](docs/SETUP_PLATFORMS.md).

### Conectar plataformas (OAuth automático)

`serve-assets` levanta el servidor de assets + un Cloudflare tunnel, descubre la URL pública, la escribe en `.env` como `PUBLIC_BASE_URL`, e imprime los redirect URIs. Conecta cada cuenta abriendo en el navegador:

- TikTok: `PUBLIC_BASE_URL/oauth/tiktok/start`
- Meta (IG+FB): `PUBLIC_BASE_URL/oauth/meta/start`

Los tokens se guardan solos en `.env`. Guía detallada por plataforma: [docs/SETUP_PLATFORMS.md](docs/SETUP_PLATFORMS.md).

Para ver el checklist y las URLs actuales sin levantar el tunnel:

```bash
xai-automation init-system            # imprime URLs + checklist
xai-automation init-system --write-env # además persiste PUBLIC_BASE_URL/LLM en .env
```

## Inicializar base SQLite

```bash
xai-automation init-db
```

## Ejecutar un ciclo (run once)

```bash
xai-automation run-once
```

## macOS (MacBook local)

### 1) Setup app

```bash
cd ai-content-automation
bash scripts/macos_setup_app.sh
```

### 2) Scheduler nativo (launchd)

Instala 3 jobs:

- run-once cada 15 min
- process-queue cada 10 min
- asset server en `ASSET_SERVER_PORT` (para `PUBLIC_BASE_URL`)

```bash
cd ai-content-automation
APP_DIR="$(pwd)" bash scripts/macos_install_launchd.sh
```

Logs:

- `out/logs/run.out.log`
- `out/logs/publish.out.log`
- `out/logs/assets.out.log`

## Validación E2E (preflight)

Valida variables y conectividad a:

- X API (recent search)
- NVIDIA API (DeepSeek chat/completions)
- Higgsfield MCP (tools/list)

```bash
xai-automation preflight
```

Sin red (solo valida variables):

```bash
xai-automation preflight --no-network
```

## Costos y logs

Variables opcionales para control de capa gratuita de Higgsfield:

- `HIGGSFIELD_COST_PER_VIDEO_USD=0.0`
- `HIGGSFIELD_FREE_TIER_MONTHLY_USD=0.0` (0 = deshabilitado)
- `HIGGSFIELD_FREE_TIER_MONTHLY_VIDEOS=0` (0 = deshabilitado)

Ver costos del mes (acumulado + eventos):

```bash
xai-automation costs
```

Listar errores de APIs (persistidos en SQLite):

```bash
xai-automation errors --limit 50
```

Ver detalle de un error:

```bash
xai-automation error --id <ERROR_ID>
```

## Cloudflare Tunnel (URL pública)

- Setup completo: [docs/TUNNEL_SETUP.md](file:///Users/pablo/Documents/demo_huggis/ai-content-automation/docs/TUNNEL_SETUP.md)
- Variables:
  - `ENABLE_CLOUDFLARE_TUNNEL=true`
  - `WEBHOOK_PORT=8088`
  - `CLOUDFLARE_TUNNEL_TOKEN=` (vacío = modo efímero; con token = dominio fijo)

## Inicialización (URLs + checklist)

Imprime redirect URIs, enlaces OAuth, template de assets y un checklist por plataforma basado en tu `PUBLIC_BASE_URL`:

```bash
xai-automation init-system             # imprime el reporte
xai-automation init-system --write-env # además persiste PUBLIC_BASE_URL/LLM en .env
# (equivalente legacy: python3 scripts/init_system.py)
```

## Cola de publicación

- Si `REQUIRE_APPROVAL=true`, el ciclo deja items en `awaiting_approval`.
- Aprobar un job:

```bash
xai-automation approve-job --job-id <JOB_ID>
```

- Procesar publicación:

```bash
xai-automation process-queue --limit 10
```

## Instagram (nota importante)

Para publicar Reels vía Graph API necesitas que el video sea accesible por una URL pública. Configura:

- `PUBLIC_BASE_URL=https://tu-dominio-publico/`

El sistema asume que `PUBLIC_BASE_URL/assets/<JOB_ID>/video.mp4` apunta al archivo generado (se copia en `out/assets/<JOB_ID>/video.mp4`).

## Tests

```bash
pytest
```

## Debian 12 (self-hosted)

Ruta recomendada de instalación:

- `/opt/ai-content-automation`
- env: `/etc/xai-automation/xai.env`

### 1) Instalar dependencias del sistema

```bash
sudo bash scripts/debian12_install.sh
```

### 2) Instalar app (venv + deps + DB)

```bash
sudo mkdir -p /opt
sudo cp -R . /opt/ai-content-automation
cd /opt/ai-content-automation
sudo bash scripts/debian12_setup_app.sh
```

### 3) Configurar env

```bash
sudo mkdir -p /etc/xai-automation
sudo cp /opt/ai-content-automation/.env /etc/xai-automation/xai.env
sudo chmod 600 /etc/xai-automation/xai.env
```

### 4) Habilitar systemd (scheduler + publish + asset server)

```bash
sudo APP_DIR=/opt/ai-content-automation bash scripts/debian12_enable_systemd.sh
```

### 5) Publicación Instagram (PUBLIC_BASE_URL)

El servidor de assets queda en:

- `http://<tu-servidor>:<ASSET_SERVER_PORT>/assets/<JOB_ID>/video.mp4`

Configura `PUBLIC_BASE_URL` en `/etc/xai-automation/xai.env` para que apunte a esa base pública.
