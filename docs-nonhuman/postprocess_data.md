# Postprocesar Data

Los datasets crudos normalmente se guardan en:

```bash
/home/autobrik/NONHUMAN/wbcd-icra-2026-data-collection/outputs
```

## 1. Postprocesar un Dataset

Corre esto desde la raiz del repo:

```bash
cd /home/autobrik/NONHUMAN/wbcd-icra-2026-data-collection
source .venv_data_collection/bin/activate

python gear_sonic/scripts/postprocess_dataset.py \
  --dataset-path outputs/<raw_dataset_name> \
  --output-path outputs/<raw_dataset_name>_postprocessed \
  --hf-repo-id NONHUMAN-RESEARCH/<raw_dataset_name>_postprocessed
```

Este wrapper corre:

- `gear_sonic/scripts/process_dataset.py`
- `gear_sonic/scripts/remove_discarded_episodes.py`

Tambien genera:

- `meta/episodes_stats.jsonl`
- `README.md`
- `preview/metadata.csv`
- `preview/videos/`

El `--output-path` no debe existir. Si hay una salida vieja o fallida, borrala antes de volver a correr:

```bash
rm -rf outputs/<raw_dataset_name>_postprocessed
```

Validacion rapida:

```bash
wc -l outputs/<raw_dataset_name>_postprocessed/meta/episodes.jsonl
wc -l outputs/<raw_dataset_name>_postprocessed/meta/episodes_stats.jsonl
```

Ambos conteos deben coincidir.

Usa el dataset postprocesado v2.1 para subir, visualizar o entrenar cuando el consumidor soporte LeRobot v2.1. Convierte a v3 solo cuando una herramienta lo requiera, por ejemplo `lerobot/annotate`.

## 2. Subir el Dataset v2.1 Postprocesado

```bash
hf repo create NONHUMAN-RESEARCH/<raw_dataset_name>_postprocessed \
  --repo-type dataset \
  --exist-ok

hf upload NONHUMAN-RESEARCH/<raw_dataset_name>_postprocessed \
  outputs/<raw_dataset_name>_postprocessed \
  . \
  --repo-type dataset
```

Si el dataset se va a cargar desde un Hugging Face Space, hazlo publico:

```bash
hf repos settings NONHUMAN-RESEARCH/<raw_dataset_name>_postprocessed \
  --repo-type dataset \
  --public
```

Si un Space muestra un error como `Unexpected token ... Internal Server Error`, primero revisa que el repo del dataset sea publico.

## 3. Opcional: Convertir a LeRobot v3 para Anotar

Usa esto solo si el dataset debe cargarse en `lerobot/annotate`.

Crea un entorno separado para LeRobot v3:

```bash
cd /home/autobrik/NONHUMAN/wbcd-icra-2026-data-collection

uv python install 3.12
uv venv .venv_lerobot_v3 --python 3.12
source .venv_lerobot_v3/bin/activate

uv pip install "lerobot @ git+https://github.com/huggingface/lerobot.git"
uv pip install "lerobot[dataset]" pandas pyarrow datasets jsonlines huggingface-hub
```

Convierte el dataset postprocesado:

```bash
python -m lerobot.scripts.convert_dataset_v21_to_v30 \
  --repo-id NONHUMAN-RESEARCH/<raw_dataset_name>_postprocessed_v3 \
  --root outputs/<raw_dataset_name>_postprocessed \
  --push-to-hub true
```

Si hace falta, crea primero el repo v3:

```bash
hf repo create NONHUMAN-RESEARCH/<raw_dataset_name>_postprocessed_v3 \
  --repo-type dataset \
  --exist-ok
```

Haz publico el repo v3:

```bash
hf repos settings NONHUMAN-RESEARCH/<raw_dataset_name>_postprocessed_v3 \
  --repo-type dataset \
  --public
```

El dataset v3 debe contener:

```text
data/chunk-000/file-000.parquet
meta/episodes/chunk-000/file-000.parquet
meta/info.json
meta/stats.json
meta/tasks.parquet
videos/<video_key>/chunk-000/file-000.mp4
```

Checks locales rapidos:

```bash
find outputs/<raw_dataset_name>_postprocessed_v3/meta -maxdepth 3 -type f
find outputs/<raw_dataset_name>_postprocessed_v3/videos -type f
```

En `lerobot/annotate`, usa una de las video keys de `meta/info.json`, por ejemplo:

```text
observation.images.ego_view
observation.images.right_wrist
```

## Ejemplo

```bash
python gear_sonic/scripts/postprocess_dataset.py \
  --dataset-path outputs/push_panda_toilet_paper_s2 \
  --output-path outputs/push_panda_toilet_paper_s2_postprocessed \
  --hf-repo-id NONHUMAN-RESEARCH/push_panda_toilet_paper_s2_postprocessed
```

```bash
python -m lerobot.scripts.convert_dataset_v21_to_v30 \
  --repo-id NONHUMAN-RESEARCH/push_panda_toilet_paper_s2_postprocessed_v3 \
  --root outputs/push_panda_toilet_paper_s2_postprocessed \
  --push-to-hub true
```
