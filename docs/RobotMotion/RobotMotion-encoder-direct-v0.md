# RobotMotion encoder direct (v0): dataset VLA -> SONIC encoder 0

Este documento describe el flujo propuesto para usar el encoder **`g1` / `mode_id: 0`** de SONIC a partir de una politica VLA entrenada con el dataset exportado por `gear_sonic/scripts/run_data_exporter.py`.

La idea central es que el VLA no predice torques ni comandos de motor de bajo nivel. El VLA predice una referencia robotica de movimiento:

- `q_body`: posiciones de los 29 joints corporales del G1.
- `root_quat`: orientacion root/base deseada.
- `left_hand_joints` y `right_hand_joints`: 7 joints por mano.

Para el nuevo enfoque, los joints corporales y los joints de ambas manos se extraen desde `observation.state`.

La orientacion root sale de `observation.root_orientation`, que el exporter guarda desde `base_quat`.

---

## 1. Observaciones requeridas por encoder 0

En `gear_sonic_deploy/policy/release/observation_config.yaml`, el modo `g1` esta definido como:

```yaml
- name: "g1"
  mode_id: 0
  required_observations:
    - encoder_mode_4
    - motion_joint_positions_10frame_step5
    - motion_joint_velocities_10frame_step5
    - motion_anchor_orientation_10frame_step5
```

Por tanto, el encoder recibe:

| Observacion | Dim | Fuente final |
|---|---:|---|
| `encoder_mode_4` | 4 | Interno del runtime. Para `g1`: `[0, 0, 0, 0]`. |
| `motion_joint_positions_10frame_step5` | 290 | 10 frames x 29 joints corporales. |
| `motion_joint_velocities_10frame_step5` | 290 | 10 frames x 29 velocidades corporales. |
| `motion_anchor_orientation_10frame_step5` | 60 | 10 frames x orientacion relativa 6D. |

Dimension total antes del encoder:

```text
4 + 290 + 290 + 60 = 644D
```

El encoder produce despues el `token_state` que consume la policy SONIC/WBC.

---

## 2. Salida del VLA

La accion por timestep queda:

```text
q_body             29D
root_quat           4D
left_hand_joints    7D
right_hand_joints   7D
-----------------------
total              47D
```

Si GR00T/VLA produce chunks:

```text
action_chunk = H x 47D
```

El adapter temporal toma ese chunk, aplica RTC si corresponde, y reconstruye las observaciones internas que espera SONIC encoder 0.

---

## 3. Origen de los labels en el dataset

El exporter construye `observation.state` en `gear_sonic/scripts/run_data_exporter.py`, dentro de `_add_data_frame_sonic()`:

```text
whole_q = robot_model.get_configuration_from_actuated_joints(
    body_actuated_joint_values=proprio["body_q"],
    left_hand_actuated_joint_values=proprio["left_hand_q"],
    right_hand_actuated_joint_values=proprio["right_hand_q"],
)

frame_data["observation.state"] = whole_q
```

Eso significa que `observation.state` ya contiene cuerpo y manos en una misma configuracion completa del robot. Por eso, para RobotMotion:

| Target VLA | Dim | Fuente primaria |
|---|---:|---|
| `q_body` | 29 | `observation.state`, extrayendo y reordenando los 29 joints corporales. |
| `root_quat` | 4 | `observation.root_orientation`. |
| `left_hand_joints` | 7 | `observation.state`, indices de mano izquierda. |
| `right_hand_joints` | 7 | `observation.state`, indices de mano derecha. |

Los campos `teleop.left_hand_joints` y `teleop.right_hand_joints` tambien pueden estar guardados, pero no son necesarios como labels primarios si se quiere que el VLA aprenda la referencia robotica ejecutada/observada desde `observation.state`.

---

## 4. Indices desde `observation.state`

La forma recomendada es usar el `RobotModel`, porque evita hardcodear indices y queda consistente con el URDF/supplemental info:

```python
q = frame["observation.state"]

q_body_supplemental = robot_model.get_body_actuated_joints(q)
left_hand_joints = robot_model.get_hand_actuated_joints(q, "left")
right_hand_joints = robot_model.get_hand_actuated_joints(q, "right")
```

Estas funciones estan definidas en `decoupled_wbc/control/robot_model/robot_model.py`:

- `get_body_actuated_joint_indices()`
- `get_hand_actuated_joint_indices(side)`
- `get_body_actuated_joints(q)`
- `get_hand_actuated_joints(q, side)`
- `get_configuration_from_actuated_joints(...)`

El orden semantico de los joints actuados del G1 esta en `decoupled_wbc/control/robot_model/supplemental_info/g1/g1_supplemental_info.py`.

### Orden corporal del supplemental info

`get_body_actuated_joints(q)` entrega los 29 joints en el orden del supplemental info:

```text
left_hip_pitch_joint
left_hip_roll_joint
left_hip_yaw_joint
left_knee_joint
left_ankle_pitch_joint
left_ankle_roll_joint
right_hip_pitch_joint
right_hip_roll_joint
right_hip_yaw_joint
right_knee_joint
right_ankle_pitch_joint
right_ankle_roll_joint
waist_yaw_joint
waist_roll_joint
waist_pitch_joint
left_shoulder_pitch_joint
left_shoulder_roll_joint
left_shoulder_yaw_joint
left_elbow_joint
left_wrist_roll_joint
left_wrist_pitch_joint
left_wrist_yaw_joint
right_shoulder_pitch_joint
right_shoulder_roll_joint
right_shoulder_yaw_joint
right_elbow_joint
right_wrist_roll_joint
right_wrist_pitch_joint
right_wrist_yaw_joint
```

Para encoder 0, revisar si la ruta usada espera el orden IsaacLab de `gear_sonic/envs/env_utils/joint_utils.py` (`G1_ISAACLab_ORDER`). Si es asi, `q_body_supplemental` debe reordenarse antes de entrar al adapter:

```text
supplemental_to_isaaclab =
[
  0, 6, 12,
  1, 7, 13,
  2, 8, 14,
  3, 9,
  15, 22,
  4, 10,
  16, 23,
  5, 11,
  17, 24,
  18, 25,
  19, 26,
  20, 27,
  21, 28,
]
```

Entonces:

```python
q_body = q_body_supplemental[supplemental_to_isaaclab]
```

### Indices estaticos de respaldo

Si no se puede instanciar `RobotModel`, los indices inferidos del URDF actual `gear_sonic/data/robot_model/model_data/g1/g1_29dof_with_hand.urdf` son:

```text
body_full_indices =
[
  0, 1, 2, 3, 4, 5,
  6, 7, 8, 9, 10, 11,
  12, 13, 14,
  15, 16, 17, 18, 19, 20, 21,
  29, 30, 31, 32, 33, 34, 35,
]

left_hand_full_indices =
[22, 23, 24, 27, 28, 25, 26]

right_hand_full_indices =
[36, 37, 38, 41, 42, 39, 40]
```

La version directa para extraer `q_body` en orden IsaacLab desde `observation.state` es:

```text
isaaclab_full_indices =
[
  0, 6, 12,
  1, 7, 13,
  2, 8, 14,
  3, 9,
  15, 29,
  4, 10,
  16, 30,
  5, 11,
  17, 31,
  18, 32,
  19, 33,
  20, 34,
  21, 35,
]
```

Estos indices son un respaldo documental. La implementacion debe preferir nombres de joints o `RobotModel`, porque si cambia el URDF o el `modality.json`, los indices hardcoded pueden quedar desfasados.

---

## 5. Variables guardadas que importan

| Variable dataset | Uso en RobotMotion |
|---|---|
| `observation.images.ego_view` | Entrada visual principal del VLA. |
| `observation.images.left_wrist` | Entrada visual opcional para grasp, si existe. |
| `observation.images.right_wrist` | Entrada visual opcional para grasp, si existe. |
| `observation.state` | Fuente primaria para `q_body`, `left_hand_joints` y `right_hand_joints`. |
| `observation.root_orientation` | Fuente primaria para `root_quat`; viene de `base_quat`. |
| `observation.init_base_quat` | Reconstruccion offline de heading; no es salida del VLA. |
| `observation.cpp_rotation_offset` | `init_ref_data_root_rot_array_` exportado; no es salida del VLA. |
| `teleop.delta_heading` | Yaw acumulado; normalmente 0 si no se uso yaw por joystick. |

Variables utiles solo como comparacion/debug:

| Variable dataset | Uso recomendado |
|---|---|
| `teleop.left_hand_joints` | Comparar mano comandada por teleop vs mano observada en `observation.state`. |
| `teleop.right_hand_joints` | Comparar mano comandada por teleop vs mano observada en `observation.state`. |
| `teleop.body_quat_w` | Alternativa/ablation desde SMPL/PICO; no es primera opcion para encoder 0. |
| `action.wbc` | Accion previa/ejecutada por WBC; util para debug, no como primer target VLA. |

---

## 6. Construccion de las observaciones del encoder 0

### 6.1 `encoder_mode_4`

No viene del dataset ni del VLA. Lo fija el deploy a partir del modo de la referencia:

```text
encoder_mode_4 = [current_motion_->GetEncodeMode(), 0, 0, 0]
```

Para `mode_id = 0`:

```text
encoder_mode_4 = [0, 0, 0, 0]
```

### 6.2 `motion_joint_positions_10frame_step5`

Fuente durante entrenamiento:

```text
q_body <- observation.state[body indices]
```

Fuente durante inferencia:

```text
q_body <- VLA/RTC output
```

Dimension:

```text
10 frames x 29 joints = 290D
```

La ruta mas fiel al runtime es mantener una trayectoria densa a 50 Hz y dejar que SONIC tome los frames `t, t+5, ..., t+45`.

### 6.3 `motion_joint_velocities_10frame_step5`

No hace falta que el VLA prediga velocidades. Se calculan desde `q_body`.

Si el chunk esta a 50 Hz:

```text
dt = 0.02 s
qdot[i] = (q_body[i] - q_body[i-1]) / dt
```

Si se calculan directamente entre puntos `step5`:

```text
dt_step = 5 * 0.02 = 0.1 s
qdot_step[i] = (q_body_step[i] - q_body_step[i-1]) / dt_step
```

Para inferencia real se recomienda generar/mantener una referencia densa y derivar con `dt = 0.02 s`; asi coincide mejor con el loop de control.

### 6.4 `motion_anchor_orientation_10frame_step5`

`motion_anchor_orientation` no debe ser predicho directamente por el VLA. Se reconstruye a partir de:

- `q_ref_root`: root quat de la referencia.
- `q_base_current`: orientacion base actual del robot medida por runtime/IMU.
- `init_base_quat`: base quat capturado al reset de heading.
- `init_ref_root_quat`: root quat inicial de la referencia.
- `delta_heading`: yaw acumulado, si existe.

La implementacion esta en `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/src/g1_deploy_onnx_ref.cpp`:

- `UpdateHeadingState()` captura `init_base_quat` desde `state_logger_->GetLatest(...)` y setea `init_ref_data_root_rot_array_` desde `current_motion_->BodyQuaternions(...)`.
- `ComputeApplyDeltaHeading()` calcula la alineacion de heading:

```text
q_align =
  heading(init_base_quat) * inverse_heading(init_ref_root_quat)

si delta_heading != 0:
  q_align =
    yaw(delta_heading) * q_align
```

- `GatherMotionAnchorOrientationMutiFrame(...)` toma el root quat futuro de la referencia, aplica el heading, lo compara contra la base actual del robot y lo convierte a 6D:

```text
q_ref_aligned =
  q_align * q_ref_root

q_relative =
  inverse(q_base_current) * q_ref_aligned

motion_anchor_orientation =
  rot6d(q_relative)
```

La representacion `rot6d` son las primeras dos columnas de la matriz de rotacion relativa, aplanadas por filas:

```text
[R00, R01, R10, R11, R20, R21]
```

Fuentes concretas:

| Termino | Inferencia real | Reconstruccion offline |
|---|---|---|
| `q_ref_root` | `root_quat` predicho por VLA/RTC. | `observation.root_orientation` del frame futuro usado como label. |
| `q_base_current` | `base_quat` medido por `state_logger_` en C++. | `observation.root_orientation[t]`. |
| `init_base_quat` | Interno C++; se captura al reset de heading. | `observation.init_base_quat`. |
| `init_ref_root_quat` | Primer/current root quat de `current_motion_`. | `observation.cpp_rotation_offset` o primer `root_quat` de la referencia. |
| `delta_heading` | Interno C++; acumulado desde `heading_increment`. | `teleop.delta_heading`. |

Si el flujo no usa joystick de yaw:

```text
heading_increment = 0
delta_heading ~= 0
```

En ese caso, la orientacion anchor sigue siendo necesaria, pero se reconstruye con el root quat predicho y el base quat medido, sin pedirle al VLA que prediga `delta_heading`.

---

## 7. Protocolo de inferencia propuesto

1. El VLA produce un chunk `H x 47D`.
2. RTC suaviza y selecciona la ventana de ejecucion.
3. El adapter separa `q_body`, `root_quat`, `left_hand_joints` y `right_hand_joints`.
4. El adapter calcula `joint_vel` desde `q_body`.
5. El adapter construye una referencia compatible con encoder 0:
   - `joint_pos`: `[N, 29]`
   - `joint_vel`: `[N, 29]`
   - `body_quat_w` o `body_quat`: `[N, 4]`
   - `frame_index`: `[N]`
   - `left_hand_joints`: `[7]`
   - `right_hand_joints`: `[7]`
   - `heading_increment`: `[1]`, normalmente 0 si no hay yaw autonomo
6. C++ carga esa referencia en `MotionSequence`.
7. El encoder 0 construye sus observaciones requeridas.
8. SONIC/WBC produce comandos de alta frecuencia para el G1.

---

## 8. Flujo global

```text
Dataset VLA
  observation.images.*
  observation.state
    -> q_body
    -> left_hand_joints
    -> right_hand_joints
  observation.root_orientation
    -> root_quat
        |
        v
Training labels
  H x 47D
        |
        v
GR00T-style VLA
        |
        v
Action chunk H x 47D
        |
        v
RTC
        |
        v
Encoder-0 adapter
  encoder_mode_4                         [0,0,0,0]
  motion_joint_positions_10frame_step5   from q_body
  motion_joint_velocities_10frame_step5  finite difference
  motion_anchor_orientation_10frame_step5 from root_quat + runtime base quat + heading state
        |
        v
SONIC encoder -> token_state -> SONIC/WBC policy -> Unitree G1
```

---

## 9. Responsabilidades

| Componente | Responsabilidad |
|---|---|
| VLA | Predecir chunks de referencia robotica `H x 47D`. |
| RTC | Suavizar y hacer consistente la salida temporal del VLA. |
| Adapter encoder 0 | Construir `joint_pos`, `joint_vel`, `body_quat_w`, `frame_index` y manos. |
| Runtime C++ | Medir `base_quat`, mantener heading state y reconstruir `motion_anchor_orientation`. |
| SONIC encoder | Convertir las observaciones `g1` a `token_state`. |
| SONIC/WBC policy | Ejecutar balance, postura y control fisico de alta frecuencia. |
