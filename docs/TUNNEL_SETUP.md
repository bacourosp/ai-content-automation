## Cloudflare Tunnel (cloudflared)

Este proyecto puede exponer un puerto HTTP local a internet usando Cloudflare Tunnel (sin ngrok).

### Instalación (macOS)

```bash
brew install cloudflared
```

### Variables (.env)

- `ENABLE_CLOUDFLARE_TUNNEL=true`
- `WEBHOOK_PORT=8088`
- `CLOUDFLARE_TUNNEL_TOKEN=` (vacío = modo efímero)

### Modo efímero (sin cuenta)

1) Asegura que tu servidor HTTP esté usando `WEBHOOK_PORT`.
2) Arranca el servidor con túnel habilitado:

```bash
ENABLE_CLOUDFLARE_TUNNEL=true CLOUDFLARE_TUNNEL_TOKEN= python3 -m xai_automation.cli serve-assets
```

En logs verás:

```
=== TUNNEL ACTIVE === Public URL: `https://....trycloudflare.com`
```

### Modo fijo (dominio propio con cuenta gratuita)

Requiere una cuenta Cloudflare gratuita y un dominio agregado a Cloudflare.

1) Autenticar cloudflared:

```bash
cloudflared tunnel login
```

2) Crear un tunnel:

```bash
cloudflared tunnel create xai-webhook
```

3) Enrutar DNS a un subdominio:

```bash
cloudflared tunnel route dns xai-webhook webhook.tudominio.com
```

4) Obtener un token (desde el dashboard o con `cloudflared tunnel token`):

```bash
cloudflared tunnel token xai-webhook
```

5) Ejecutar el tunnel usando el token:

```bash
CLOUDFLARE_TUNNEL_TOKEN='<PEGA_AQUI_EL_TOKEN>' cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN"
```

6) Integrar con la app (recomendado):

- Define en tu `.env`:
  - `ENABLE_CLOUDFLARE_TUNNEL=true`
  - `CLOUDFLARE_TUNNEL_TOKEN=<PEGA_AQUI_EL_TOKEN>`
  - `WEBHOOK_PORT=<PUERTO_LOCAL>`
- Arranca:

```bash
python3 -m xai_automation.cli serve-assets
```

El túnel se mantiene activo con watchdog y se reinicia automáticamente si el proceso cae.

