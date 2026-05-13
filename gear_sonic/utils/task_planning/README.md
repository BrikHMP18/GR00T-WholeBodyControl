# VLM-Only Shelf Planner

Util minimo para llamar VLMs con una imagen del shelf.

```text
imagen -> OpenRouter VLM -> respuesta cruda
```

No parsea, no valida y no hace benchmark. Solo guarda lo que responde el modelo.

## Setup

```bash
cd /home/autobrik/NONHUMAN/wbcd-icra-2026-deployment/gear_sonic/utils/task_planning
UV_CACHE_DIR=.uv-cache uv sync
cp .env.example .env
```

`.env`:

```bash
OPENROUTER_API_KEY=...
OPENROUTER_MODEL1=qwen/qwen3-vl-8b-instruct
OPENROUTER_MODEL2=google/gemini-2.5-flash
OPENROUTER_MODEL3=openai/gpt-4.1-mini
OPENROUTER_MAX_TOKENS=256
OPENROUTER_REASONING_EFFORT=none
```

## Uso

Una imagen con todos los modelos definidos en `.env`:

```bash
./run_vlm_only_planner.sh \
  --input /home/autobrik/NONHUMAN/wbcd-icra-2026-deployment/media/wbcd_competition/shelf/shelf-image1.png \
  --all
```

Una carpeta:

```bash
./run_vlm_only_planner.sh \
  --input /home/autobrik/NONHUMAN/wbcd-icra-2026-deployment/media/wbcd_competition/shelf \
  --all
```

Lista custom de modelos:

```bash
./run_vlm_only_planner.sh \
  --input /path/to/image.png \
  --models qwen/qwen3-vl-8b-instruct,google/gemini-2.5-flash
```

Uso directo:

```bash
uv run python vlm_only_planner.py \
  --image /path/to/image.png \
  --model qwen/qwen3-vl-8b-instruct \
  --output result.json
```

## Output

Los resultados se guardan en:

```text
outputs_test/vlm_only-YYYY-MM-DD_HH-MM-SS/
  qwen__qwen3-vl-8b-instruct/
  google__gemini-2.5-flash/
  openai__gpt-4.1-mini/
```

Cada `*_result.json` tiene:

```json
{
  "image": "/path/to/image.png",
  "model": "qwen/qwen3-vl-8b-instruct",
  "inference_time_seconds": 1.234,
  "vlm_output": "{...respuesta cruda del modelo...}"
}
```

Si la llamada falla:

```json
{
  "image": "/path/to/image.png",
  "model": "qwen/qwen3-vl-8b-instruct",
  "inference_time_seconds": 1.234,
  "error": "...",
  "vlm_output": null
}
```

## Prompt

El prompt usado esta en:

```text
vlm_only_prompt.txt
```
