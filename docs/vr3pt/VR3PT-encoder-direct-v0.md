# VR3PT encoder direct (v0): fuentes de las observaciones requeridas en modo `teleop`

Este documenta **solo el bloque `encoder_modes` → `name: "teleop"`** en `gear_sonic_deploy/policy/release/observation_config.yaml` (`mode_id: 1` y `required_observations`). Responde: *antes y dentro de* `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/src/g1_deploy_onnx_ref.cpp`, ¿de dónde salen los valores por frame que forman el input del encoder (ventana de 10 frames donde aplica)?

Observaciones cubiertas:

- `encoder_mode_4` (4D)
- `motion_joint_positions_lowerbody_10frame_step5` (120D)
- `motion_joint_velocities_lowerbody_10frame_step5` (120D)
- `vr_3point_local_target` (9D)
- `vr_3point_local_orn_target` (12D)
- `motion_anchor_orientation` (6D)

Referencia de envío Python (Pico / manager): `gear_sonic/scripts/pico_manager_thread_server.py` (`PoseStreamer.run_once` → `pack_pose_message`).

---

## “Frame” y `MotionSequence`

Un **frame** es un timestep de `MotionSequence` (una fila en el stream mergeado). En ZMQ, un mensaje puede traer **N frames** (p. ej. `smpl_pose` con shape `[N, 21, 3]`). El alineamiento temporal usa `frame_index` (vector monotónico de enteros).

Merge en C++:

- `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/include/input_interface/zmq_endpoint_interface.hpp` (`DecodeIntoMotionSequence`)
- `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/include/input_interface/streamed_motion_merger.hpp` (`MergeIncomingData`)
- `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/include/motion_data_reader.hpp` (`struct MotionSequence`)

---

## Transporte ZMQ desde `pico_manager_thread_server.py`

Layout del mensaje packed:

- `[topic_bytes][header JSON fijo ~1280 B][payload binario concatenado]`
- Header: `fields: [{ name, dtype, shape }, …]`.

Implementación:

- Sender: `gear_sonic/utils/teleop/zmq/zmq_planner_sender.py::pack_pose_message`
- Receiver: `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/include/input_interface/zmq_packed_message_subscriber.hpp`

Por defecto **`pack_pose_message(..., version=3)`**, es decir protocolo **v3** (requiere SMPL + `joint_pos` + `joint_vel` + `body_quat` + índices de frame según validación del receiver; ver `zmq_endpoint_interface.hpp`).

Campos relevantes que **sí** publica `PoseStreamer` en el dict `numpy_data` al enviar poses (entre otros):

| Campo ZMQ | Shape típica (PoseStreamer) | Rol |
|-----------|-----------------------------|-----|
| `smpl_pose` | `[N, 21, 3]` | Pose SMPL (axis-angle por joint interno tras `compute_from_body_poses`). |
| `smpl_joints` | `[N, 24, 3]` | Joints locales SMPL proyectados. |
| `body_quat_w` | `[N, 4]` | Orientación root (wxyz) alineada con el pipeline SMPL/Pico. |
| `joint_pos` | `[N, 29]` | **Targets** G1 IsaacLab order (29 DOF); en el script, muñecas vía mapping SMPL→G1 (`joint_pos[23:29]`), resto puede quedar 0 si no se rellena. |
| `joint_vel` | `[N, 29]` | En el script actual: **`np.zeros((N, 29))`** (relleno explícito de ceros). |
| `vr_position` | `(9,)` flatten | Posiciones 3 puntos × 3 (muñeca I, muñeca D, cuello) en frame **calibrado** (`ThreePointPose` + `_process_3pt_pose`). |
| `vr_orientation` | `(12,)` flatten | Quaterniones wxyz por punto, mismo orden que `vr_position`. |
| `frame_index` | vector int | Índices de frame para el merger. |

Origen Pico en cadena corta:

1. `PicoReader._run` → `xrt.get_body_joints_pose()` → `body_poses_np` (~24 joints × 7, frame Unity).
2. `PoseStreamer`: `compute_from_body_poses(...)` produce tensores tipo SMPL; acumula `smpl_pose`, `smpl_joints`, `body_quat_w` en buffers.
3. `three_point.process_smpl_pose(sample["body_poses_np"], …)` produce `vr_3pt_pose` `(3, 7)` por fila `[x,y,z, qw,qx,qy,qz]` (muñecas SMPL 22–23, cuello 12 respecto root, con calibración G1).

> La palabra **`motion_*` en los nombres de observación del encoder** significa datos almacenados en **`current_motion_` / `MotionSequence`** dentro del deploy, que se rellenan **después** de decodificar el ZMQ, no “estado histórico `his_*` del robot medido por encoders físicos.

---

## Registro de dimensiones y gatherers (`g1_deploy_onnx_ref.cpp`)

El mapa nombre → tamaño está en `GetObservationRegistry()`:

- `encoder_mode_4` → **4** → `GatherEncoderMode(..., fill_zeros_num=3)`
- `motion_joint_positions_lowerbody_10frame_step5` → **120** → `GatherMotionJointPositionsMultiFrame(buf, offset, num_frames=10, step_size=5, joint_indexes=lower_body_joint_mujoco_order_in_isaaclab_index)`
- `motion_joint_velocities_lowerbody_10frame_step5` → **120** → `GatherMotionJointVelocitiesMultiFrame(...)` mismos argumentos.
- `vr_3point_local_target` → **9** → `GatherVR3PointPosition`
- `vr_3point_local_orn_target` → **12** → `GatherVR3PointOrientation`
- `motion_anchor_orientation` → **6** → `GatherMotionAnchorOrientationMutiFrame(buf, offset, num_frames=1, step_size=1, orientation_mode=0)` (orientación anchor “full base quaternion” vs referencia).

Índices inferiores (12 joints en orden Isaac dentro de los 29), definidos en `policy_parameters.hpp`:

- `lower_body_joint_mujoco_order_in_isaaclab_index = {0, 3, 6, 9, 13, 17, 1, 4, 7, 10, 14, 18}`.

Ventana **`10frame_step5`**: para cada índice de ventana `frame_idx ∈ {0,…,9}`, el gatherer usa el frame objetivo  
`target_frame = current_frame_ + frame_idx * 5` (con clamp al final del motion cuando hace falta).  
**Dimensiones**: 12 joints × 10 snapshots = **120** por observación posición/velocidad.

---

## Fuente exacta de cada observación (`teleop`)

### 1) `encoder_mode_4` (4D)

**No es one-hot.** Implementación (`GatherEncoderMode`):

- `encoder_mode_4[0] = static_cast<float>(current_motion_->GetEncodeMode())`
- `encoder_mode_4[1..3] = 0`

**En `pico_manager_thread_server.py`**: el dict `numpy_data` **no** incluye ningún campo `encoder_mode_4`. El valor sale del objeto `motion` en C++.

En `ZMQEndpointInterface`, al mergear streams con protocolo establecido:

- `protocol v1` → `SetEncodeMode(0)`
- `protocol v2 / v3` → `SetEncodeMode(2)` (“SMPL-based” según ese bloque).

El YAML marca teleop como `mode_id: 1`; eso debe coincidir con `GetEncodeMode() == 1` **solo si** la configuración o la carga runtime del binario establece ese modo sobre el motion (por ejemplo inicialización/`initial_encoder_mode_`, CSV, teclas según builds), porque **el stream Pico por defecto con `pack_pose_message(..., version=3)` invoca la ruta que setea `encode_mode` a `2`**, no `1`. Para despliegue VR3PT con encoder entrenado en `mode_id: 1`, hay que garantizar ese override explícito en el lado C++/config del deploy.

---

### 2) `motion_joint_positions_lowerbody_10frame_step5` (120D)

**Fuente inmediata en C++**: filas futuras de `current_motion_->JointPositions(target_frame)` para los **12 índices inferiores** listados arriba, vía `GatherMotionJointPositionsMultiFrame`.

**Procedencia ZMQ / Pico**:

- Esos vectores **`joint_pos` por frame** llegan desde el campo homónimo del mensaje (protocolo v3 **requiere** `joint_pos` con shape `[N, 29]`). El merger los escribe en `MotionSequence`.

**Qué construye Python en `PoseStreamer`**:

- Rellena `joint_pos` de longitud **29** cada frame (`PoseStreamer.run_once`): las **articulaciones de muñeca** `(23–28)` se derivan del mapping código SMPL codo/muñeca → roll/pitch/yaw G1; **otras articulaciones** del vector pueden permanecer en **0** en el código mostrado. Por tanto los **DOFs inferiores** dentro de ese `joint_pos` **solo reflejan el teleop Pico en la medida en que ese vector se rellene** para piernas/torso; si el script deja piernas en cero, el encoder verá zeros en esas articulaciones aunque el cuerpo SMPL sí se mueve (`smpl_pose`/`smpl_joints` son otros campos).

**Interacción opcional**: si `has_upper_body_data_` está activo, el gather de **todas** las 29 articulaciones puede sobrescribir torso/brazos con buffers externos; para el caso **solo lower-body indices**, siguen siendo las componentes seleccionadas de la fila ya fusionada con esa lógica cuando aplica globalmente.

---

### 3) `motion_joint_velocities_lowerbody_10frame_step5` (120D)

Igual que posiciones pero leyendo `current_motion_->JointVelocities(target_frame)` sobre los mismos 12 índices (`GatherMotionJointVelocitiesMultiFrame`).

**Procedencia ZMQ / Pico**:

- Protocolo v3 espera **`joint_vel`**. En **`pico_manager_thread_server.py`**, `PoseStreamer` pone **`joint_vel = np.zeros((N, 29))`** al empaquetar. Así, **la velocidad de referencia vista por el encoder es nula en streaming Pico actual**, salvo otro merged o herramienta que envíe `joint_vel` no nulo.

Cuando **`operator_state.play`** es falso en el deploy, este gather também **rellena velocidades con 0**.

---

### 4) `vr_3point_local_target` (9D) y `vr_3point_local_orn_target` (12D)

**Ruta preferida cuando hay datos VR externos** (`has_vr_3point_data_ == true`): copiar los buffers poblados desde el interface de entrada (ZMQ/ROS/etc.):

- Posición: `vr_3point_position_buffer_` (9 doubles)
- Orientación: `vr_3point_orientation_buffer_` (12 doubles, wxyz por punto × 3)

En **`zmq_endpoint_interface.hpp`** el decoder marca presencia VR si existe el campo **`vr_position`** (9 elementos); **`vr_orientation`** actualiza cuaterniones cuando viene en el mismo mensaje.

**Equivalencia con Pico**:

- `PoseStreamer` asigna `vr_position = vr_3pt_pose[:, :3].flatten()` y `vr_orientation = vr_3pt_pose[:, 3:].flatten()`.
- Orden físico filas del `vr_3pt_pose`: **muñeca izquierda, muñeca derecha, cuello** (`_process_3pt_pose` / `ThreePointPose` tras calibración).

**Sin stream VR válido**, `GatherVR3PointPosition/Orientation` pueden calcular desde `current_motion_` usando índices de body parts y offsets (ver mismo `.cpp`): es ruta replay/dataset, no Pico en vivo.

Comentario en código: durante teleop con buffers externos **`vr_3point_local_target` coincide prácticamente con la variante `vr_3point_local_target_compliant`** (compliance opcional está en otros caminos).

---

### 5) `motion_anchor_orientation` (6D)

**No llega ya empaquetada con ese nombre** desde `pico_manager_thread_server.py`. Se calcula en C++ en `GatherMotionAnchorOrientationMutiFrame` (misma matemática base que describe el doc SMPL para orientación tipo “anchor”):

- **Referencia / motion**: `current_motion_->BodyQuaternions(target_frame)[0]`, poblado desde el stream por **`body_quat_w`**/`body_quat` (entre los campos que sí envía Pico: `body_quat_w`).
- **Robot**: **`base_quat`** desde `state_logger_->GetLatest(...)` — **no** viene del Pico; viene del estado estimado/medido del robot.

Se aplica política de **heading** vía `apply_delta_heading` (buffers `heading_state_buffer_`, `init_ref_data_root_rot_array_`, rutina `ComputeApplyDeltaHeading`). Con `orientation_mode=0`, `left_quat` es la **orientación base completa del robot**.

Representación salida (**6D**): primeras **dos columnas** de la matriz de rotación de `base_to_ref_quat`, aplanadas **por filas** (\( \mathbb{R}^{3\times2} \rightarrow 6 \) floats), coherente con el comentario en el código del `.cpp`.

**Resumen de procedencia Pico indirecta**:

- La parte **referencia temporal** sí está ligada al **root quaternion** derivado del body tracking cuando fluye como `body_quat_w`; la parte **robot** es local al deploy sobre hardware.

---

## Resumen rápido: cadena Pico → observación encoder

| Observación | ¿Campo literal en mensaje Pico? | Origen efectivo para VR3PT en vivo |
|-------------|--------------------------------|-------------------------------------|
| `encoder_mode_4` | No | `GetEncodeMode()` en C++; cuidado con mismatch **YAML `mode_id` 1** vs **`pack_pose_message` v3 → SetEncodeMode(2)** si no hay override. |
| `motion_joint_positions_lowerbody_*` | Indirectamente: **`joint_pos` [N,29]** deducido/de stream | Fill del merger; Pico script rellena al menos wrists; piernas pueden ser **0** si no se mapean. |
| `motion_joint_velocities_lowerbody_*` | **`joint_vel` [N,29]** | En Pico actual: **ceros**. |
| `vr_3point_local_target` | **`vr_position` (9)** | `three_point.process_smpl_pose` ← `body_poses_np` ← XRT. |
| `vr_3point_local_orn_target` | **`vr_orientation` (12)** | Misma cadena que posición (quats wxyz). |
| `motion_anchor_orientation` | No (se calcula) | **`body_quat_w`** en referencia + **`base_quat`** robot + heading en C++. |

---

## Concatenación al encoder ONNX (solo modo `teleop` del YAML)

Suma lineal típica de las piezas habilitadas en `required_observations` para ese modo:

\[ 4 + 120 + 120 + 9 + 12 + 6 = 271 \]

dimensión flotantes **antes** de la interna **`encoder.dimension`** (p. ej. 64-D `token_state` en ONNX), definida aparte en el mismo `observation_config.yaml`.
