# Playbook — Simulación MuJoCo → Recolección de Data para WBCD Track 1

Guía reproducible end-to-end: de un clone limpio del repo a trayectorias teleoperadas en formato LeRobot, listas para fine-tunear GR00T N1.5 sobre el Track 1 (Logistics Picking).

**Soporta dos perfiles de hardware:**
- **AMD / CPU only** → Ruta B (primaria de este doc).
- **NVIDIA / CUDA** → Ruta A (apéndice; camino oficial de NVIDIA).

**Regla de ejecución:** una fase a la vez. Cada fase tiene un criterio de validación explícito. No avanzar si falla.

**Docs relacionados en `notes/`:**
- `pipeline_WBCD.md` — estrategia System 1/2, distribución del dataset.
- `Logistic_picking.md` — spec oficial del Track 1.
- `SONIC.md` — paper de referencia (universal token space, §2.4.3 GR00T connector).
- `README_teleop.md` — instalación del servicio PICO (una vez por máquina).
- `task_logistic_picking_implementation.md` — plan de la task custom `LMLogisticsPicking`.

---

## Contexto arquitectónico

NVIDIA documenta dos rutas oficiales para este repo; ambas asumen GPU NVIDIA:

| Ruta oficial | Documentada en | Bloqueador en AMD |
|---|---|---|
| **venvs uv + C++ deploy** | `docs/source/getting_started/quickstart.md` | `gear_sonic_deploy/deploy.sh` exige CUDA+TensorRT |
| **Docker pre-built** | `docs/source/references/decoupled_wbc.md` | Prerequisito textual: "NVIDIA Container Toolkit" |

Este playbook construye una **tercera ruta no oficial** para AMD/CPU: replica el entorno del `Dockerfile.deploy` oficial dentro de un conda env dedicado (Python 3.10 + ROS 2 Humble + deps idénticas a las del Docker), y usa el stack Python `decoupled_wbc/` en lugar del C++ deploy. La receta canónica de la Fase 4 viene directamente del Dockerfile oficial (`decoupled_wbc/docker/Dockerfile.deploy:99-127`).

Motivo de la fricción en Ruta B: el repo está **empaquetado para Docker, no bare-metal**. `pyproject.toml` referencia paths fuera del paquete (funciona en Docker, rompe con setuptools moderno), deps escondidas en extras `[full]`, el fork G1 de `robosuite` solo existe como clon de GitHub y no en PyPI. El playbook documenta cada parche.

---

## Entornos

| Caso de uso | Env | Python | Instalador |
|---|---|---|---|
| Sim MuJoCo standalone (sanity, sandbox teclado) | `.venv_sim` (uv) | 3.10 | `bash install_scripts/install_mujoco_sim.sh` |
| Teleop PICO (streamer) | `.venv_teleop` (uv) | 3.10 | `bash install_scripts/install_pico.sh` |
| **Recolección Ruta B (primaria)** | **`wbcd_ros` (conda)** | **3.10** | **Fase 4** |
| Recolección Ruta A (NVIDIA only) | `.venv_data_collection` (uv) | 3.10 | `bash install_scripts/install_data_collection.sh` |

**Reglas:**
- Activar **un solo env por terminal**. Mezclar `wbcd_ros` con venvs uv contamina `PYTHONPATH` y rompe imports.
- No correr `install_scripts/install_ros.sh` sobre `conda base`. Degrada el solver `libmamba` si tu base es Python 3.12. La Fase 4 resuelve ROS en un env dedicado.

---

# SETUP (Fases 0-4)

## Fase 0 — Pre-flight

```bash
cd /home/autobrik/NONHUMAN/GR00T-WholeBodyControl
git lfs install
git lfs pull
python check_environment.py
```

**Válido:** `[+] PASS` en Python 3.10+, git-lfs, gear_sonic instalado. Los `[X]` de Isaac Lab / TensorRT / CUDA no aplican para Ruta B.

---

## Fase 1 — `.venv_sim` + sim sanity

```bash
bash install_scripts/install_mujoco_sim.sh
source .venv_sim/bin/activate
python gear_sonic/scripts/run_sim_loop.py
```

**Válido:** ventana MuJoCo con el G1 de pie. `Ctrl+C` para salir.

**Fallback gráfico:** `MUJOCO_GL=glfw python ...` o `MUJOCO_GL=egl python ...`.

---

## Fase 2 — Cámaras onboard (dos terminales)

El viewer es cliente ZMQ; el sim actúa como server con `--enable_offscreen --enable_image_publish`.

**Terminal A — server:**
```bash
source .venv_sim/bin/activate
python gear_sonic/scripts/run_sim_loop.py --enable_offscreen --enable_image_publish
```

**Terminal B — client:**
```bash
source .venv_sim/bin/activate
python gear_sonic/scripts/run_camera_viewer.py --camera-host localhost --camera-port 5555
```

**Válido:** ventana `SONIC Camera Viewer` con stream `ego_view` activo. Esa es la única observación visual permitida por el reglamento del Track 1.

---

## Fase 3 — `.venv_data_collection` (solo Ruta A)

Saltar si vas a Ruta B:

```bash
bash install_scripts/install_data_collection.sh
```

---

## Fase 4 — `wbcd_ros` (solo Ruta B)

Conda env dedicado Python 3.10 con ROS 2 Humble + stack del repo, siguiendo la receta del `Dockerfile.deploy` oficial.

### 4.0 Pre-check de conda

Si `conda --version` tira `Error while loading conda entry point: conda-libmamba-solver (undefined symbol: sqlite3_deserialize)`, reinstala miniforge desde cero:

```bash
rm -rf /home/autobrik/miniforge3
sed -i '/# >>> conda initialize >>>/,/# <<< conda initialize <<</d' ~/.bashrc
cd ~ && wget -q https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh -b -p /home/autobrik/miniforge3
/home/autobrik/miniforge3/bin/conda init bash
# Cerrar terminal, abrir nueva.
```

### 4.1 Crear env + instalar ROS

```bash
conda config --set solver libmamba
conda create -y -n wbcd_ros python=3.10
conda activate wbcd_ros

conda config --env --add channels conda-forge
conda config --env --add channels robostack-staging

# Stub requerido por ros-humble-ros-workspace post-link:
touch /home/autobrik/miniforge3/setup.sh

conda install -y ros-humble-desktop
```

### 4.2 Patch de `pyproject.toml` (bug de empaquetado)

`decoupled_wbc/pyproject.toml` referencia `../README.md` y `../LICENSE`, que setuptools moderno bloquea:

```bash
cd /home/autobrik/NONHUMAN/GR00T-WholeBodyControl
sed -i 's|^readme = "\.\./README\.md"|# readme removed: points outside package|' decoupled_wbc/pyproject.toml
sed -i 's|^license = {file = "\.\./LICENSE"}|# license removed: points outside package|' decoupled_wbc/pyproject.toml
```

### 4.3 Deps del repo (secuencia canónica)

```bash
source "$CONDA_PREFIX/setup.bash"

# 1. SDK Unitree
pip install -e external_dependencies/unitree_sdk2_python

# 2. Paquetes principales con extras idénticos al Docker oficial
GIT_LFS_SKIP_SMUDGE=1 pip install \
  -e "decoupled_wbc[full,dev]" \
  -e "gear_sonic[sim]"

# 3. robosuite fork G1 (NO publicado en PyPI)
cd external_dependencies
git clone https://github.com/xieleo5/robosuite.git
cd robosuite
git checkout leo/support_g1_locomanip
pip install -e .
cd /home/autobrik/NONHUMAN/GR00T-WholeBodyControl

# 4. gr00trobocasa (registra REGISTERED_LOCOMANIPULATION_ENVS)
pip install -e decoupled_wbc/dexmg/gr00trobocasa

# 5. Dep opcional de robosuite que usa el fork G1
pip install robosuite_models

# 6. Macros privadas de robosuite (evita warnings en runtime)
python external_dependencies/robosuite/robosuite/scripts/setup_macros.py

# 7. PYTHONPATH al repo root, sesión + persistente
export PYTHONPATH=/home/autobrik/NONHUMAN/GR00T-WholeBodyControl:$PYTHONPATH
grep -q "GR00T-WholeBodyControl" ~/.bashrc || \
  echo 'export PYTHONPATH=/home/autobrik/NONHUMAN/GR00T-WholeBodyControl:$PYTHONPATH' >> ~/.bashrc
```

### 4.4 Verificación

```bash
python -c "import rclpy, lerobot, mujoco, robosuite, robocasa, decoupled_wbc, unitree_sdk2py; print('ALL OK')"
```

**Válido:** `ALL OK`.

### Uso habitual en Ruta B

Cada terminal nueva:

```bash
conda activate wbcd_ros
source "$CONDA_PREFIX/setup.bash"
```

---

# SANDBOX (opcional)

## Fase 5 — Walk con teclado sin PICO

Stack ligero `decoupled_wbc/sim2mujoco/`. Mundo vacío, sin cámaras ni tasks. Sirve para familiarizarse con SONIC y las 3 alturas de pelvis del Track 1 (upright/bent/crouched).

### 5.1 Deps y fixes (una vez)

```bash
source .venv_sim/bin/activate
uv pip install onnxruntime pynput
```

**Fix YAML** (`decoupled_wbc/sim2mujoco/resources/robots/g1/g1_gear_wbc.yaml`) — apunta a checkpoints inexistentes:

```yaml
# Antes:
policy_path: "policy/ft92.onnx"
walk_policy_path: "policy/ft109.onnx"
# Después:
policy_path: "policy/GR00T-WholeBodyControl-Balance.onnx"
walk_policy_path: "policy/GR00T-WholeBodyControl-Walk.onnx"
```

**Fix Python** (`decoupled_wbc/sim2mujoco/scripts/run_mujoco_gear_wbc.py:248`) — CPU fallback:

```python
# Antes:
return torch.tensor(ort_outs[0], device="cuda:0")
# Después:
return torch.tensor(ort_outs[0], device="cuda:0" if torch.cuda.is_available() else "cpu")
```

### 5.2 Correr

```bash
source .venv_sim/bin/activate
python decoupled_wbc/sim2mujoco/scripts/run_mujoco_gear_wbc.py
```

| Tecla | Acción |
|---|---|
| `W` / `S` | Avanzar / retroceder |
| `A` / `D` | Strafe izquierda / derecha |
| `Q` / `E` | Rotar |
| `Z` | Parar (reset de comandos) |
| `1` / `2` | Subir / bajar pelvis |
| `3/4/5/6/7/8` | Roll / pitch / yaw del torso |
| `M` / `N` | Frecuencia de paso |

**Reset de pose:** botón `Reset` del panel *Simulation* del viewer MuJoCo, o `Backspace` con foco en la ventana.

---

# PIPELINE (Ruta B)

## Fase 6 — Smoke test sin PICO

Levanta task `PnPBottle` con `--body-control-device dummy`, corre 50 steps (`--ci-test --ci-test-mode unit`), valida stack end-to-end.

```bash
python decoupled_wbc/control/main/teleop/run_sync_sim_data_collection.py \
  --task-name PnPBottle \
  --body-control-device dummy \
  --hand-control-device dummy \
  --enable-onscreen \
  --renderer mjviewer \
  --ci-test \
  --ci-test-mode unit
```

**Válido:** ventana MuJoCo con G1 + mesa + botella; consola termina con `Episode saved. CI test: Completed...`.

**Nota tyro:** flags con `--kebab-case` (no `key=value`). Para ver todas las opciones: `--help`.

### 6.1 Tasks RoboCasa disponibles

| Task | Descripción |
|---|---|
| `GroundOnly` | Solo locomoción |
| `PnPBottle` | Pick botella → place |
| `LMBottlePnP` | Variante locomanipulation |
| `LMPickBottle` | Solo pick |
| `LMPnPAppleToPlate` | **Réplica del PoC del paper SONIC §2.4.3** |
| `LMNavPickBottle` | Nav + pick |
| `VisualReach` | Reach a target visual |

Para crear `LMLogisticsPicking` ver `task_logistic_picking_implementation.md`.

---

## Fase 7 — PICO (setup)

Ver `README_teleop.md`. Verificación rápida:

```bash
pgrep -a runService || /opt/apps/roboticsservice/runService.sh &
```

Headset puesto → PC Service → status `WORKING`, Tracking = `Head + Controller`.

---

## Fase 8 — Recolección con PICO sobre task existente

Arrancar con `LMPnPAppleToPlate` — replica el PoC del paper, baseline conocido antes de entrar a task custom.

**Terminal A — streamer PICO:**
```bash
source .venv_teleop/bin/activate
python gear_sonic/scripts/pico_manager_thread_server.py --manager
```

**Terminal B — data collection:**
```bash
conda activate wbcd_ros
source "$CONDA_PREFIX/setup.bash"

python decoupled_wbc/control/main/teleop/run_sync_sim_data_collection.py \
  --task-name LMPnPAppleToPlate \
  --body-control-device vive \
  --hand-control-device dummy \
  --enable-onscreen \
  --manual-control \
  --save-img-obs
```

**Flags clave:**
- `--body-control-device vive` → lee stream PICO (nombre histórico del driver).
- `--manual-control` → toggle de start/stop con botón del PICO.
- `--save-img-obs` → frames de cámara al dataset (obligatorio para GR00T).

**Output:** el script imprime `<dataset_dir>` al inicio. Estructura LeRobot:
```
<dataset_dir>/
  meta/{episodes.jsonl, info.json, modality.json}
  data/chunk-000/episode_*.parquet
  videos/
```

---

## Fase 9 — Playback del episodio

```bash
python decoupled_wbc/control/main/teleop/playback_sync_sim_data.py \
  --task-name LMPnPAppleToPlate \
  --dataset <path_al_dataset_dir> \
  --use-wbc-goals \
  --enable-onscreen
```

**Válido:** G1 reproduce la trayectoria en MuJoCo sin caerse.

---

## Fase 10 — Task custom `LMLogisticsPicking`

Plan detallado en `task_logistic_picking_implementation.md`. Resumen:

1. Crear `decoupled_wbc/dexmg/gr00trobocasa/robocasa/environments/locomanipulation/locomanip_logistics.py` heredando de `LMEnvBase` (patrón de `LMBottlePnP`).
2. Escena `LabArena` + `lab_shelf` asset (3 niveles lógicos a `spawn_id` 0/2/4 del modelo).
3. Registro automático vía metaclass `LocoManipulationEnvMeta` — basta con que la clase se importe.
4. Lanzar con `--task-name LMLogisticsPicking` sustituyendo en el comando de Fase 8.

**Tiempo estimado:** 2-3 días para MVP.

---

## Fase 11 — Volumen (empírico)

**Referencia oficial única** (SONIC §2.4.3):

> *"Using the **300 trajectories** collected with the 3-point teleoperation interface, we fine-tune a GR00T N1.5 model [...] the system attains a **95% success rate over 20 trials**"*

Cubre task trivial (apple-to-plate, 1 ítem, 1 altura). El paper reconoce: *"scaling to richer task distributions is left for future work"*. Track 1 (10 ítems × 3 alturas) es substancialmente más ancho; NVIDIA no publicó guía numérica.

**Rango externo:** ALOHA/ACT 50-100, Diffusion Policy 100-200, RT-1 ~185, π0 400-1000. Track 1 cae en 500-2500 demos.

**Protocolo empírico — escalar por sprints con criterio de parada:**

| Sprint | Demos | Eval | Criterio de avance |
|---|---|---|---|
| S0 | 50 | 20 holdout | ≥ 40% → S1, si no revisar task design |
| S1 | 500 | 20 holdout | ≥ 70% → S2 opcional, si no S2 obligatorio |
| S2 | 1500 | 50 holdout | ≥ 85% → detenerse |

**Distribución por posture** (priorizando valor de puntos del reglamento):

| Posture | Puntos | % dataset |
|---|---|---|
| Crouched (bottom shelf) | +10 | 40% |
| Bent (middle shelf) | +8 | 35% |
| Upright (top shelf) | +5 | 25% |

**Tiempo por sprint:** S0 ~25-50 min, S1 ~4-8 h, S2 ~12-25 h (acumulados, a ~30-60 s/trayectoria).

El dataset de producción se decide por success rate en holdout, no por un número fijo de demos.

---

# APÉNDICE A — Ruta NVIDIA

Para colegas con GPU NVIDIA. Tres comandos:

```bash
./docker/run_docker.sh --install --root         # pull del Docker image
./docker/run_docker.sh --root                   # entrar al container
python decoupled_wbc/scripts/deploy_g1.py --interface sim --simulator robocasa \
  --camera_host localhost --sim_in_single_process --image-publish --enable-offscreen \
  --env_name PnPBottle --hand_control_device=pico --body_control_device=pico
```

Requiere: Ubuntu 22.04, NVIDIA GPU + driver, Docker, NVIDIA Container Toolkit.

Esquiva toda la fricción de empaquetado de Ruta B: pyproject paths, forks privados, PYTHONPATH, setuptools. Todo pre-resuelto en el image `docker.io/nvgear/decoupled_wbc`. Documentación oficial completa: `docs/source/references/decoupled_wbc.md`.

---

# Resumen de ejecución (Ruta B)

```
SETUP (una vez):
  0. git lfs + check_environment.py           [5 min]
  1. install_mujoco_sim.sh + sim sanity       [10-15 min]
  2. camera viewer (dos terminales)           [5 min]
  4. conda wbcd_ros + ROS + pip deps          [20-40 min]

SANDBOX (opcional):
  5. walk con teclado                         [15 min]

PIPELINE:
  6. smoke test PnPBottle dummy               [10 min]
  7. PICO setup                               [5 min]
  8. recolección con PICO sobre task base     [30 min + tiempo de demos]
  9. playback validación                      [10 min]
 10. crear LMLogisticsPicking                 [2-3 días]
 11. volumen empírico S0→S1→S2                [parar cuando success ≥ 85%]

SIGUIENTE: fine-tune GR00T N1.5 en GPU alquilada (Runpod/Lambda ~$0.5/h).
```
