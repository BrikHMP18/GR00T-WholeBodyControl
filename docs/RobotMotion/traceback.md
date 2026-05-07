# Traceback RobotMotion: variables para inferencia con encoder 0

Este archivo resume, desde el codigo, que variables necesita el flujo **RobotMotion / g1 / encoder 0**, de donde vienen en el dataset VLA y como se reconstruyen durante inferencia.

La conclusion practica es:

```text
VLA output por timestep = 47D

q_body             29D  <- observation.state
root_quat           4D  <- observation.root_orientation
left_hand_joints    7D  <- observation.state
right_hand_joints   7D  <- observation.state
```

Los campos `teleop.left_hand_joints` y `teleop.right_hand_joints` existen, pero para este enfoque no son necesarios como labels primarios. Sirven como senal comandada/debug. Si queremos aprender lo que realmente queda en la configuracion robotica, las manos salen de `observation.state`.

---

## 1. Observaciones requeridas por el encoder 0

`gear_sonic_deploy/policy/release/observation_config.yaml` define para `mode_id: 0`:

| Variable encoder 0 | Dim | Fuente final |
|---|---:|---|
| `encoder_mode_4` | 4D | Interno C++: `[0, 0, 0, 0]` para `mode_id=0`. |
| `motion_joint_positions_10frame_step5` | 290D | `q_body` del VLA/adapter: 10 x 29. |
| `motion_joint_velocities_10frame_step5` | 290D | Derivada temporal de `q_body`; no se predice. |
| `motion_anchor_orientation_10frame_step5` | 60D | Calculada desde `root_quat` + base quat actual + heading state. |

Total:

```text
644D -> encoder -> token_state
```

---

## 2. Variables guardadas por el exporter

En `gear_sonic/scripts/run_data_exporter.py`, `_add_data_frame_sonic()` construye:

```text
observation.state = whole_q
```

donde `whole_q` se arma con:

```text
proprio["body_q"]
proprio["left_hand_q"]
proprio["right_hand_q"]
```

usando `robot_model.get_configuration_from_actuated_joints(...)`.

Luego `_add_cpp_state_features()` agrega:

```text
observation.root_orientation      <- proprio["base_quat"]
observation.cpp_rotation_offset   <- proprio["init_ref_data_root_rot_array"]
observation.init_base_quat        <- proprio["init_base_quat"]
teleop.delta_heading              <- proprio["delta_heading"]
```

Por tanto, para entrenar el VLA:

| Variable dataset | Uso primario |
|---|---|
| `observation.images.ego_view` | Entrada visual del VLA. |
| `observation.images.left_wrist` | Entrada visual opcional, si existe. |
| `observation.images.right_wrist` | Entrada visual opcional, si existe. |
| `observation.state` | Fuente de `q_body`, `left_hand_joints`, `right_hand_joints`. |
| `observation.root_orientation` | Fuente de `root_quat`. |

Variables auxiliares para reconstruccion/debug:

| Variable dataset | Uso |
|---|---|
| `observation.init_base_quat` | Reconstruccion offline del heading state. |
| `observation.cpp_rotation_offset` | Root quat inicial de referencia exportado desde C++. |
| `teleop.delta_heading` | Yaw acumulado; normalmente 0 si no se uso yaw por joystick. |
| `teleop.left_hand_joints` | Comparar mano comandada vs mano observada. |
| `teleop.right_hand_joints` | Comparar mano comandada vs mano observada. |
| `teleop.body_quat_w` | Alternativa/ablation desde SMPL/PICO; no es target primario de encoder 0. |
| `action.wbc` | Debug de accion WBC; no es primer target de entrenamiento VLA. |

---

## 3. Extraccion desde `observation.state`

La ruta robusta es usar `RobotModel`, definido en `decoupled_wbc/control/robot_model/robot_model.py`:

```python
q = frame["observation.state"]

q_body_supplemental = robot_model.get_body_actuated_joints(q)
left_hand_joints = robot_model.get_hand_actuated_joints(q, "left")
right_hand_joints = robot_model.get_hand_actuated_joints(q, "right")
```

El orden de esos grupos viene de `decoupled_wbc/control/robot_model/supplemental_info/g1/g1_supplemental_info.py`.

Si el adapter/encoder espera orden IsaacLab, se debe convertir el cuerpo usando el orden de `gear_sonic/envs/env_utils/joint_utils.py` (`G1_ISAACLab_ORDER`):

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

```python
q_body = q_body_supplemental[supplemental_to_isaaclab]
```

Indices estaticos de respaldo para el URDF actual:

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

left_hand_full_indices =
[22, 23, 24, 27, 28, 25, 26]

right_hand_full_indices =
[36, 37, 38, 41, 42, 39, 40]
```

Entonces:

```python
q_body = q[isaaclab_full_indices]
left_hand_joints = q[left_hand_full_indices]
right_hand_joints = q[right_hand_full_indices]
```

Estos indices deben validarse contra `meta/info.json` o `robot_model.joint_names` del dataset final. Si cambia el URDF, se deben regenerar.

---

## 4. Salida final del VLA

| Salida VLA | Dim/timestep | Label recomendado |
|---|---:|---|
| `q_body` | 29D | `observation.state` -> 29 joints corporales, orden requerido por encoder/adapter. |
| `root_quat` | 4D | `observation.root_orientation`. |
| `left_hand_joints` | 7D | `observation.state` -> indices mano izquierda. |
| `right_hand_joints` | 7D | `observation.state` -> indices mano derecha. |

Total:

```text
29 + 4 + 7 + 7 = 47D
```

Si GR00T/VLA predice chunks:

```text
action_chunk = H x 47D
```

---

## 5. Reconstruccion de `motion_joint_positions`

Durante entrenamiento:

```text
q_body[t] <- observation.state[t]
```

Durante inferencia:

```text
q_body[t:t+H] <- VLA/RTC output
```

El adapter mantiene una secuencia temporal y SONIC toma:

```text
t, t+5, t+10, ..., t+45
```

para construir:

```text
motion_joint_positions_10frame_step5 = 10 x 29 = 290D
```

---

## 6. Reconstruccion de `motion_joint_velocities`

El VLA no necesita producir velocidades. Se calculan en el adapter desde `q_body`.

Si la referencia esta a 50 Hz:

```text
dt = 0.02 s
qdot[i] = (q_body[i] - q_body[i-1]) / dt
```

Si se trabaja directamente con puntos separados por `step5`:

```text
dt_step = 0.1 s
qdot_step[i] = (q_body_step[i] - q_body_step[i-1]) / dt_step
```

La opcion mas consistente con el runtime es mantener la trayectoria densa a 50 Hz y dejar que el encoder submuestree a `step5`.

---

## 7. Reconstruccion de `motion_anchor_orientation`

`motion_anchor_orientation_10frame_step5` no viene como label directo y no debe ser una salida adicional del VLA. Se calcula en C++.

Archivo principal:

```text
gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/src/g1_deploy_onnx_ref.cpp
```

Funciones relevantes:

- `UpdateHeadingState()`
- `ComputeApplyDeltaHeading()`
- `GatherMotionAnchorOrientationMutiFrame(...)`

### 7.1 Estado inicial de heading

`UpdateHeadingState()` captura la orientacion real actual del robot:

```text
base_quat <- state_logger_->GetLatest(...).base_quat
init_base_quat <- base_quat
```

y captura la orientacion root inicial de la referencia:

```text
init_ref_root_quat <- current_motion_->BodyQuaternions(current_frame_)[0]
```

En el dataset exportado:

```text
init_base_quat       -> observation.init_base_quat
init_ref_root_quat   -> observation.cpp_rotation_offset
```

### 7.2 Alineacion de heading

`ComputeApplyDeltaHeading()` calcula:

```text
q_align =
  heading(init_base_quat) * inverse_heading(init_ref_root_quat)
```

Si existe yaw acumulado:

```text
q_align =
  yaw(delta_heading) * q_align
```

En tu caso, si no estas usando joystick yaw:

```text
heading_increment = 0
delta_heading ~= 0
```

Entonces no hace falta que el VLA prediga `delta_heading`.

### 7.3 Rotacion relativa robot -> referencia

`GatherMotionAnchorOrientationMutiFrame(...)` obtiene:

```text
q_base_current <- state_logger_->GetLatest(...).base_quat
q_ref_root     <- current_motion_->BodyQuaternions(target_frame)[0]
```

Luego:

```text
q_ref_aligned =
  q_align * q_ref_root

q_relative =
  inverse(q_base_current) * q_ref_aligned

motion_anchor_orientation =
  rot6d(q_relative)
```

La salida por frame es 6D:

```text
[R00, R01, R10, R11, R20, R21]
```

Para `10frame_step5`:

```text
10 x 6D = 60D
```

### 7.4 Fuentes durante inferencia

| Termino | De donde sale en inferencia |
|---|---|
| `q_ref_root` | `root_quat` producido por VLA/RTC y cargado en la referencia/motion. |
| `q_base_current` | IMU/base actual del robot via `state_logger_`. |
| `init_base_quat` | Interno de C++, capturado cuando se resetea heading. |
| `init_ref_root_quat` | Primer/current `root_quat` de la referencia cargada. |
| `delta_heading` | Interno de C++; queda 0 si no se envia `heading_increment`. |

### 7.5 Fuentes durante reconstruccion offline

| Termino | De donde sale en dataset |
|---|---|
| `q_ref_root` | `observation.root_orientation` del frame futuro. |
| `q_base_current` | `observation.root_orientation[t]`. |
| `init_base_quat` | `observation.init_base_quat`. |
| `init_ref_root_quat` | `observation.cpp_rotation_offset` o primer `observation.root_orientation` de la referencia. |
| `delta_heading` | `teleop.delta_heading`. |

La regla importante: el VLA solo predice `root_quat`. Todo lo demas para `motion_anchor_orientation` se mide o se mantiene dentro del runtime.

---

## 8. Adapter hacia SONIC

El adapter de inferencia debe construir una referencia compatible con encoder 0:

| Campo | Shape | Fuente |
|---|---:|---|
| `joint_pos` | `[N, 29]` | `q_body` del VLA/RTC. |
| `joint_vel` | `[N, 29]` | Derivada de `joint_pos`. |
| `body_quat_w` / `body_quat` | `[N, 4]` | `root_quat` del VLA/RTC, normalizado. |
| `frame_index` | `[N]` | Contador monotono del adapter. |
| `left_hand_joints` | `[7]` | Salida VLA/RTC entrenada desde `observation.state`. |
| `right_hand_joints` | `[7]` | Salida VLA/RTC entrenada desde `observation.state`. |
| `heading_increment` | `[1]` | 0 en la primera version si no hay yaw autonomo. |

---

## 9. Flujo final

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
GR00T/VLA training
  target = H x 47D
        |
        v
Inference
  VLA predicts H x 47D
        |
        v
RTC
  smoothing + receding horizon
        |
        v
Encoder-0 adapter
  joint_pos, joint_vel, body_quat_w, frame_index, hands
        |
        v
SONIC encoder 0
  encoder_mode_4
  motion_joint_positions_10frame_step5
  motion_joint_velocities_10frame_step5
  motion_anchor_orientation_10frame_step5
        |
        v
token_state -> SONIC/WBC policy -> Unitree G1
```
