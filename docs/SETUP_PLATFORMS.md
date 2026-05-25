# Configuración de plataformas (paso a paso)

Esta guía describe cómo obtener cada credencial y cómo conectar las cuentas. El flujo OAuth de TikTok y Meta es **automático**: el servidor de assets expone los callbacks y guarda los tokens en `.env` por ti.

## 0. Flujo general

```bash
# 1) Copia el ejemplo y rellena lo básico
cp .env.example .env

# 2) Crea la base de datos
xai-automation init-db

# 3) Levanta el servidor de assets + tunnel (mantenlo corriendo)
#    Esto descubre la URL pública, la escribe en .env e imprime los redirect URIs.
ENABLE_CLOUDFLARE_TUNNEL=true xai-automation serve-assets

# 4) En otra terminal, revisa el checklist y las URLs:
xai-automation init-system
```

> **URL efímera:** con tunnel sin token, la URL `*.trycloudflare.com` **cambia en cada reinicio**. Si reinicias `serve-assets`, vuelve a registrar los redirect URIs en TikTok/Meta. Para una URL fija usa un Cloudflare Named Tunnel con dominio propio (`CLOUDFLARE_TUNNEL_TOKEN` + `PUBLIC_BASE_URL`). Los tokens OAuth son de larga duración / refrescables, así que basta con conectar una vez.

---

## 1. LLM (elige uno)

### Gemini (por defecto, recomendado)
1. Entra a https://aistudio.google.com/apikey y crea una API key (tier gratuito, sin tarjeta).
2. En `.env`: `LLM_PROVIDER=gemini`, `GEMINI_API_KEY=...`, `GEMINI_MODEL=gemini-2.5-flash`.

### NVIDIA NIM / DeepSeek (alternativa)
1. Entra a https://build.nvidia.com, genera una API key.
2. En `.env`: `LLM_PROVIDER=nvidia`, `NVIDIA_API_KEY=nvapi-...`, `DEEPSEEK_MODEL=deepseek-ai/deepseek-v3.1-terminus`.

Valida con: `xai-automation preflight`

---

## 2. X (Twitter)
1. https://developer.x.com → Project/App → genera un **Bearer Token** (API v2).
2. En `.env`: `X_BEARER_TOKEN=...`
3. El cliente usa `https://api.x.com/2` (recent search / lists / user timeline).

---

## 3. TikTok (Content Posting API)
1. https://developers.tiktok.com → crea una app y añade el producto **Content Posting API** (Direct Post).
2. Solicita los scopes `video.publish` y `video.upload`.
3. En **Redirect URI** pega el que imprime el sistema: `https://TU-URL/callback/tiktok`.
4. Copia Client key/secret a `.env`: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`.
5. Conecta la cuenta abriendo en el navegador: `https://TU-URL/oauth/tiktok/start`
   → al autorizar, se guardan `TIKTOK_ACCESS_TOKEN` y `TIKTOK_REFRESH_TOKEN` en `.env`.

> El token se **refresca automáticamente** al publicar si expira (usa client key/secret + refresh token).

---

## 4. Meta (Instagram Reels + Facebook)
Requisitos: una **Página de Facebook** y una cuenta de **Instagram Business** vinculada a esa página.

1. https://developers.facebook.com → crea una app tipo **Business**.
2. Añade productos **Facebook Login** e **Instagram Graph API**.
3. Scopes: `instagram_content_publish`, `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `business_management`.
4. En **Valid OAuth Redirect URIs** pega: `https://TU-URL/callback/meta`.
5. Copia App ID/Secret a `.env`: `META_APP_ID`, `META_APP_SECRET`.
6. Conecta abriendo: `https://TU-URL/oauth/meta/start`
   → se guardan `META_ACCESS_TOKEN` (page token de larga duración), `FACEBOOK_PAGE_ID` e `INSTAGRAM_BUSINESS_ACCOUNT_ID` en `.env`.

> Instagram descarga el video desde `PUBLIC_BASE_URL/assets/<JOB_ID>/video.mp4`, por eso `serve-assets` debe seguir corriendo y `PUBLIC_BASE_URL` debe apuntar a la URL pública actual.

---

## 5. Proveedores de render de video (`RENDER_PROVIDER`)

El render es **seleccionable** para A/B-testear calidad. Elige uno con `RENDER_PROVIDER` (default `higgsfield`). Todos están **apagados** salvo que los selecciones y pongas sus claves. Generación de **imágenes** (carruseles/thumbnails) usa la **API oficial de Gemini** (`ENABLE_IMAGE_GEN=true`), no MCPs de terceros.

| Proveedor | `RENDER_PROVIDER` | Transporte | Estado / seguridad |
|---|---|---|---|
| Higgsfield | `higgsfield` | HTTP MCP | Default. URL+API key propias. |
| MCP genérico | `mcp` | HTTP MCP | Apunta a **cualquier** servidor MCP de render por HTTP que tú controles (`RENDER_MCP_URL`). Cero terceros nuevos. |
| glif | `glif` | stdio (npx **pineado**) | Oficial glif.app (MIT). **Restringido a un `GLIF_RENDER_ID` fijo** (no ejecuta glifs arbitrarios). |
| remotion-media | `remotion_media` | stdio (npx **pineado**) | Comunidad (MIT). Genera video/audio reales vía **kie.ai** (datos a terceros). |
| remotion-app | `remotion_app` | HTTP | **AVISO ACE**: ejecuta código React generado por IA. **SOLO self-host** (se rechaza URL pública). Off por defecto. |

**Excluidos por seguridad** (no integrados): `gongrzhe/image-generation` (archivado), `qhdrl12/gemini-image` (no oficial, deps sin pin → usa Gemini oficial), `mcpmarket/ai-video-generator` (procedencia no verificable), Remotion MCP oficial (solo indexa docs), `open-design` como backend (MCP read-only + daemon que ejecuta agentes).

### Configurar cada uno
- **Higgsfield:** `HIGGSFIELD_MCP_URL`, `HIGGSFIELD_API_KEY`. Si la autodetección del tool falla, fija `HIGGSFIELD_TOOL_NAME`/`HIGGSFIELD_ARG_NAME` (míralos en `preflight`).
- **mcp (genérico):** `RENDER_MCP_URL` (+ `RENDER_API_KEY`, `RENDER_TOOL_NAME`, `RENDER_ARG_NAME`, `RENDER_INPUT_KIND=spec|prompt`).
- **glif:** `GLIF_API_TOKEN` (glif.app/settings/api-tokens) + `GLIF_RENDER_ID` (el id del glif que renderiza). Comando pineado por defecto `npx -y @glifxyz/glif-mcp-server@0.9.9` (requiere Node).
- **remotion-media:** `KIE_API_KEY` (kie.ai). Comando pineado `npx -y remotion-media-mcp@1.2.2` (requiere Node).
- **remotion-app (avanzado):** self-host `https://github.com/mcp-use/remotion-mcp-app`, luego `REMOTION_APP_MCP_URL=http://localhost:3000/mcp`. Solo URLs locales/privadas.
- **Imágenes (Gemini oficial):** `ENABLE_IMAGE_GEN=true` + `GEMINI_API_KEY`; `GEMINI_IMAGE_MODEL=gemini-2.5-flash-image`.

> Versiones de los paquetes npm pineadas a propósito (mitiga supply-chain). Verifica el nombre del tool y el esquema de cada MCP contra el servidor real; son configurables por env.

---

## 6. Verificación
```bash
xai-automation preflight            # valida env + conectividad (X, LLM, Higgsfield)
xai-automation run-once             # un ciclo completo
xai-automation process-queue --limit 10
```
Si `REQUIRE_APPROVAL=true`, aprueba antes de publicar: `xai-automation approve-job --job-id <ID>`.
