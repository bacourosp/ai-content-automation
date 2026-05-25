1) Entra al proyecto:

```bash
cd /Users/pablo/Documents/demo_huggis/ai-content-automation
```

2) Ejecuta `preflight` y luego `run-once` (recomendado con el venv activo):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 -m xai_automation.cli preflight
python3 -m xai_automation.cli run-once
```

Si ya lo instalaste como comando (entrypoint), entonces sería:

```bash
xai-automation preflight
xai-automation run-once
```

Si te sale `command not found: xai-automation`, significa que no está instalado en tu PATH. En ese caso usa la forma con `python3 -m xai_automation.cli ...` (arriba), o instala el proyecto en el venv:

```bash
pip install -e .
xai-automation preflight
xai-automation run-once
```