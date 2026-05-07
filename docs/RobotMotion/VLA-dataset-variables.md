# VLA dataset variables

Este documento lista las variables que guarda el exporter VLA para el flujo SONIC/GR00T, con enfasis en el uso para **RobotMotion / encoder 0**.

Fuentes principales en el repo:

- `gear_sonic/scripts/run_data_exporter.py`
- `gear_sonic/scripts/run_data_exporter_gr00t.py`
- `gear_sonic/data/features_sonic_vla.py`
- `gear_sonic/data/features_sonic_vla_gr00t.py`

La version `run_data_exporter_gr00t.py` agrega campos `action.*` para entrenamiento con GR00T. En varios casos esos campos son copias semanticas de `teleop.*`; no significan por si mismos que la accion este desplazada a `t+1`.

---

## 1. Convencion temporal

Cada frame del dataset se guarda como un snapshot sincronizado con los ultimos mensajes disponibles:

```text
frame t:
  observation.*[t]
  teleop.*[t]
  action.*[t], si existe
```

El exporter no construye automaticamente:

```text
observation[t] -> action[t+1]
```

Para RobotMotion, si `observation.state` se usa como label de movimiento, el target futuro debe construirse en preprocessing:

```text
input:
  observation[t]

target:
  observation.state[t+1:t+H]
  observation.root_orientation[t+1:t+H]
```

---

## 2. Entradas visuales

| Variable | Shape | Dtype | Origen | Uso |
|---|---:|---|---|---|
| `observation.images.ego_view` | `[480, 640, 3]` | video | Mensaje de camara principal. | Entrada visual principal del VLA. |
| `observation.images.left_wrist` | `[480, 640, 3]` | video | Opcional si `record_wrist_cameras` esta activo. | Vista de grasp/mano izquierda. |
| `observation.images.right_wrist` | `[480, 640, 3]` | video | Opcional si `record_wrist_cameras` esta activo. | Vista de grasp/mano derecha. |

Las imagenes se agregan en `_add_images_to_frame_data()` recorriendo los features de tipo `image` o `video`.

---

## 3. Estado robotico observado

| Variable | Shape | Dtype | Origen | Uso |
|---|---:|---|---|---|
| `observation.state` | `(num_joints,)` | float64 | `whole_q` construido desde `proprio["body_q"]`, `proprio["left_hand_q"]`, `proprio["right_hand_q"]`. | Estado completo del robot. Para RobotMotion es la fuente primaria de `q_body` y manos. |
| `observation.eef_state` | `(14,)` | float64 | FK desde `whole_q`: pose de wrists izquierda/derecha. | Estado cartesiano de end-effectors; util como observacion auxiliar. |
| `observation.root_orientation` | `(4,)` | float64 | `proprio["base_quat"]`. | Orientacion base/root real del G1. Fuente primaria de `root_quat` para RobotMotion. |
| `observation.projected_gravity` | `(3,)` | float64 | Calculada desde `base_quat`. | Observacion auxiliar de orientacion/gravedad. |
| `observation.cpp_rotation_offset` | `(4,)` | float64 | `proprio["init_ref_data_root_rot_array"]`, si existe. | Reconstruccion/debug de heading; no es salida del VLA. |
| `observation.init_base_quat` | `(4,)` | float64 | `proprio["init_base_quat"]`, si existe. | Reconstruccion/debug de heading; no es salida del VLA. |

`observation.state` se arma en `_add_data_frame_sonic()`:

```text
whole_q = robot_model.get_configuration_from_actuated_joints(
    body_actuated_joint_values=proprio["body_q"],
    left_hand_actuated_joint_values=proprio["left_hand_q"],
    right_hand_actuated_joint_values=proprio["right_hand_q"],
)
```

---

## 4. Acciones WBC y token interno

| Variable | Shape | Dtype | Origen | Uso |
|---|---:|---|---|---|
| `action.wbc` | `(num_joints,)` | float64 | `whole_action_wbc` construido desde `proprio["last_action"]`, `proprio["last_left_hand_action"]`, `proprio["last_right_hand_action"]`. | Debug/analisis de accion ejecutada o reportada por WBC. No es target primario recomendado para RobotMotion. |
| `action.motion_token` | `(64,)` | float64 | `proprio["token_state"]`, si existe. | Token interno de SONIC; util para inspeccion, no como salida del VLA. |

Nota: `action.wbc` viene de `last_action`. No debe asumirse como accion futura `t+1`.

---

## 5. Teleop SMPL / PICO

Estos campos se agregan desde el mensaje SONIC/PICO cuando el stream mode usa SMPL.

| Variable | Shape | Dtype | Origen | Uso |
|---|---:|---|---|---|
| `teleop.smpl_joints` | `(72,)` | float32 | `smpl_joints` del mensaje de pose. | Referencia humana SMPL. |
| `teleop.smpl_pose` | `(63,)` | float32 | `smpl_pose` del mensaje de pose. | Pose SMPL compacta. |
| `teleop.body_quat_w` | `(4,)` | float32 | `body_quat_w` del mensaje de pose. | Orientacion cuerpo humano/PICO; ablation para encoder 0, no primera opcion. |
| `teleop.target_body_orientation` | `(6,)` | float32 | Calculada desde `teleop.body_quat_w` y `teleop.delta_heading`. | Orientacion rot6D normalizada; auxiliar. |
| `teleop.left_wrist_joints` | `(3,)` | float32 | Extraido de `joint_pos` SMPL/PICO. | Joints de muneca izquierda en modo SMPL. |
| `teleop.right_wrist_joints` | `(3,)` | float32 | Extraido de `joint_pos` SMPL/PICO. | Joints de muneca derecha en modo SMPL. |
| `teleop.smpl_frame_index` | `(1,)` | int64 | `frame_index` del mensaje de pose. | Debug/sincronizacion. |
| `teleop.left_hand_joints` | `(7,)` | float32 | Mensaje de mano/pose/planner. | Mano comandada por teleop. Debug o ablation para RobotMotion. |
| `teleop.right_hand_joints` | `(7,)` | float32 | Mensaje de mano/pose/planner. | Mano comandada por teleop. Debug o ablation para RobotMotion. |
| `teleop.stream_mode` | `(1,)` | int32 | `current_stream_mode`. | Indica modo activo de teleop/stream. |

Para RobotMotion, las manos recomendadas como label primario salen de `observation.state`, no de `teleop.left_hand_joints`/`teleop.right_hand_joints`.

---

## 6. Campos `action.*` en exporter GR00T

`run_data_exporter_gr00t.py` agrega labels `action.*` para GR00T. En el codigo actual son copias de señales teleop del mismo frame:

| Variable | Shape | Dtype | Origen | Uso |
|---|---:|---|---|---|
| `action.smpl_joints` | `(72,)` | float32 | Copia de `teleop.smpl_joints`. | Target causal para el enfoque SMPL anterior. |
| `action.body_quat_w` | `(4,)` | float32 | Copia de `teleop.body_quat_w`. | Target causal para el enfoque SMPL anterior. |
| `action.left_hand_joints` | `(7,)` | float32 | Copia de `teleop.left_hand_joints`. | Target de mano en enfoque SMPL/teleop. |
| `action.right_hand_joints` | `(7,)` | float32 | Copia de `teleop.right_hand_joints`. | Target de mano en enfoque SMPL/teleop. |

Estos campos son utiles si se entrena al VLA a imitar la interfaz teleop/SMPL. Para RobotMotion encoder 0, el target recomendado se construye desde estados roboticos futuros:

```text
q_body_future             <- observation.state[t+1:t+H]
root_quat_future          <- observation.root_orientation[t+1:t+H]
left_hand_joints_future   <- observation.state[t+1:t+H]
right_hand_joints_future  <- observation.state[t+1:t+H]
```

---

## 7. Planner / VR3PT

Estos campos se llenan cuando el stream mode usa planner/VR3PT; si no hay datos, se guardan con ceros o defaults.

| Variable | Shape | Dtype | Origen | Uso |
|---|---:|---|---|---|
| `teleop.delta_heading` | `(1,)` | float64 | `proprio["delta_heading"]`, si existe. | Yaw acumulado para heading. Normalmente 0 si no se usa yaw por joystick. |
| `teleop.planner_mode` | `(1,)` | int32 | Mensaje planner. | Modo locomocion/planner. |
| `teleop.planner_movement` | `(3,)` | float32 | Mensaje planner. | Vector de movimiento planner. |
| `teleop.planner_facing` | `(3,)` | float32 | Mensaje planner. | Direccion de facing. |
| `teleop.planner_speed` | `(1,)` | float32 | Mensaje planner. | Velocidad planner. |
| `teleop.planner_height` | `(1,)` | float32 | Mensaje planner. | Altura planner. |
| `teleop.vr_3pt_position` | `(9,)` | float32 | `vr_position` o planner. | Tres puntos VR: wrists y torso/neck. |
| `teleop.vr_3pt_orientation` | `(18,)` | float32 | `vr_orientation` convertido a rot6D. | Orientaciones 3 puntos en rot6D. |

Para el enfoque RobotMotion encoder 0, estos campos no son targets primarios. Pueden servir para analisis, ablation o para extender navegacion/heading si luego se decide aprender yaw/planner.

---

## 8. Variables recomendadas para RobotMotion encoder 0

### Entradas del VLA

```text
observation.images.ego_view
observation.images.left_wrist, opcional
observation.images.right_wrist, opcional
observation.state
observation.root_orientation
language / task instruction, si existe
```

### Labels que se deben construir en preprocessing

```text
target[t] = future reference chunk

q_body[t+1:t+H]             <- observation.state
root_quat[t+1:t+H]          <- observation.root_orientation
left_hand_joints[t+1:t+H]   <- observation.state
right_hand_joints[t+1:t+H]  <- observation.state
```

Por timestep:

```text
q_body             29D
root_quat           4D
left_hand_joints    7D
right_hand_joints   7D
-----------------------
total              47D
```

### Variables que NO debe predecir el VLA

```text
encoder_mode_4
motion_joint_velocities_10frame_step5
motion_anchor_orientation_10frame_step5
observation.init_base_quat
observation.cpp_rotation_offset
teleop.delta_heading, en la primera version si heading_increment = 0
action.motion_token
action.wbc
```

Estas variables se reconstruyen en el adapter/runtime o se usan solo para debug.
