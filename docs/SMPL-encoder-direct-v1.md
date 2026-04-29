# SMPL encoder direct (v1): fuentes de `smpl_joints`, `smpl_anchor_orientation`, `motion_joint_positions_wrists`, `encoder_mode_4`

Este doc responde **solo para modo SMPL**: *antes* de entrar a `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/src/g1_deploy_onnx_ref.cpp`, ¿de dónde salen los valores por-frame que luego terminan formando el input del encoder (ventana de 10 frames)?

En particular, documenta la **fuente real** de:

- `smpl_joints` (72D)
- `smpl_anchor_orientation` (6D)
- `motion_joint_positions_wrists` (6D)
- `encoder_mode_4` (4D)

## “Frame” (en streaming SMPL)

Un **frame** es un timestep de `MotionSequence` (una fila de datos). En ZMQ, un mensaje puede traer **1 frame o un chunk de N frames**. El alineamiento temporal se hace con `frame_index` (vector monotónico de enteros).

Los frames recibidos se **mergean** en una ventana deslizante dentro de `MotionSequence` por:

- `.../include/input_interface/zmq_endpoint_interface.hpp` (`DecodeIntoMotionSequence`)
- `.../include/input_interface/streamed_motion_merger.hpp` (`MergeIncomingData`)
- `.../include/motion_data_reader.hpp` (`struct MotionSequence`)

## Qué se envía por ZMQ (modo SMPL) *antes del .cpp*

El transporte usa un “packed message”:

- layout: `[topic_bytes]["header JSON" fijo 1280B][payload binario concatenado]`
- el header describe `fields: [{name,dtype,shape}, ...]` y el receiver decodifica los bytes según eso.

Implementación:

- Sender (Python): `gear_sonic/utils/teleop/zmq/zmq_planner_sender.py::pack_pose_message`
- Receiver (C++): `.../include/input_interface/zmq_packed_message_subscriber.hpp`

### Campos mínimos que el receiver exige para “motion” SMPL (protocol v2/v3)

En `.../include/input_interface/zmq_endpoint_interface.hpp`:

- Para motion protocols (v1/v2/v3) **siempre** requiere:
  - `body_quat_w` (o `body_quat`)
  - `frame_index` (o `last_smpl_global_frames`)
- Para SMPL:
  - **v2** requiere `smpl_joints` + `smpl_pose` (y *opcionalmente* `joint_pos`/`joint_vel`)
  - **v3** requiere `smpl_joints` + `smpl_pose` + `joint_pos` + `joint_vel`

Detalles de shapes (receiver C++):

- `body_quat_w`/`body_quat`: soporta shape `[N, 4]` (1 body) o `[N, num_bodies, 4]`. Se interpreta como **wxyz**.
- `smpl_joints`: se espera típicamente `[N, 24, 3]`.
- `smpl_pose`: se espera típicamente `[N, 21, 3]` (axis-angle por joint pose; el receiver lo trata como `[N, num_poses, 3]`).
- `joint_pos`, `joint_vel`: se espera `[N, 29]` (29 DOFs G1 en **IsaacLab order**).

> Importante: el encoder SMPL en C++ usa `smpl_joints`/`anchor_orientation`/`wrists`/`encoder_mode_4`, pero el **protocolo ZMQ** puede requerir campos extra (`smpl_pose`, `body_quat_w`, `frame_index`) para que el streaming sea aceptado/mergeable.

## Fuente exacta de las 4 variables (modo SMPL)

### 1) `smpl_joints` (72D)

- **Fuente**: llega **por ZMQ** en el campo `smpl_joints` (típicamente shape `[N,24,3]`, dtype `f32` o `f64`).
- **Ruta**:
  - `ZMQEndpointInterface::DecodeIntoMotionSequence()` decodifica `smpl_joints` → `decoded_smpl_joints`
  - `StreamedMotionMerger` lo copia a `MotionSequence::smpl_joints_`
  - En el `.cpp`, el gatherer `GatherMotionSmplJointsMultiFrame(..., num_frames=1)` lo aplana a 72 floats (o a 720 si se pide `10frame_step1`)

**Esto sí viene del VR**, en el sentido de que la fuente upstream suele ser el body tracking (PICO/SMPL) y se publica como `smpl_joints` por ZMQ.

### 2) `motion_joint_positions_wrists` (6D)

Esta variable **NO sale del estado del robot**. Sale de `current_motion_` (la “motion/reference/stream” actual) y se lee como **subset** de `joint_pos` (los targets de joints de la *motion*, no feedback).

- **Fuente inmediata en C++**: `MotionSequence::JointPositions(frame)` dentro de `current_motion_`, tomado vía `GatherMotionJointPositionsMultiFrame(..., joint_indexes=wrist_joint_isaaclab_order_in_isaaclab_index)`.
- **De dónde viene ese `joint_pos`**:
  - Si estás en ZMQ streaming SMPL **protocol v3**, `joint_pos` es **requerido** y por tanto viene del mensaje ZMQ.
  - Si estás en SMPL **v2**, `joint_pos` es **opcional**: si no lo mandas, *no hay de dónde* llenar wrists correctamente para `motion_joint_positions_wrists_*` (a menos que estés reproduciendo una motion pregrabada desde CSV, no streaming).

Índices exactos (IsaacLab order):

- `wrist_joint_isaaclab_order_in_isaaclab_index = [23, 24, 25, 26, 27, 28]` (ver `.../include/policy_parameters.hpp`).
- En el doc de reverse engineering se usan índices por-joint `joint_pos[23:29]` para describir esos 6 valores.

**Entonces, en teleop VR/SMPL típico**:

- `motion_joint_positions_wrists` viene **indirectamente del VR**, porque el sender (Python) suele:
  - estimar pose humana (SMPL)
  - aplicar un mapping humano→robot para muñecas (roll/pitch/yaw por lado)
  - escribir esos 6 DOFs dentro de `joint_pos[23:29]` (en el mensaje ZMQ)

No confundir con observaciones de **estado del robot** en el `.cpp`, que se llaman `his_*` (ej. `his_body_joint_positions_*`) y salen de `state_logger_`. Aquí la palabra `motion_*` significa “referencia/motion/stream”, no “robot”.

### 3) `smpl_anchor_orientation` (6D)

Esta variable **no se envía por ZMQ**. Se **calcula en C++** en `GatherMotionAnchorOrientationMutiFrame(...)` usando dos fuentes:

- **Referencia/motion**: `current_motion_->BodyQuaternions(target_frame)[0]`
  - Esto viene del ZMQ field `body_quat_w`/`body_quat` (streaming) o de `body_quat.csv` (motion pregrabada).
- **Estado del robot**: `base_quat` desde `state_logger_->GetLatest(...)`
  - Esto es IMU/estado actual del robot, *no viene del VR*.

Y además usa el estado de heading (`heading_state_buffer_` + `init_ref_data_root_rot_array_`) para construir `apply_delta_heading`, que se aplica a la referencia antes de hacer el diff.

**Qué representa**: un “relative orientation” entre el robot (en alguna variante: full base quat / heading-only / refheading) y la orientación del anchor/root de la referencia, expresado como **rotación 6D**:

- compute:
  - `new_ref_root_rot = apply_delta_heading ⊗ ref_data_root_rot`
  - `base_to_ref_quat = inv(left_quat) ⊗ new_ref_root_rot`
  - `R = quat_to_rotation_matrix(base_to_ref_quat)`
  - `6D = R[:,:2]` aplanado **row-wise** \(\rightarrow\) 6 floats

En resumen:

- `body_quat_w` (reference/motion) **sí** suele venir del VR/SMPL upstream (por ZMQ)
- `base_quat` (robot) **no** viene del VR; viene del robot runtime (`state_logger_`)
- `smpl_anchor_orientation` es un *join* de ambas cosas (robot state + reference root quat)

### 4) `encoder_mode_4` (4D)

En este deployment, `encoder_mode_4` **no es one-hot** del tipo `[0,0,0,1]`.

Es:

- `encoder_mode_4[0] = current_motion_->GetEncodeMode()`
- `encoder_mode_4[1..3] = 0`

Fuente de `encode_mode`:

- En streaming ZMQ, `ZMQEndpointInterface` fija `motion->SetEncodeMode(...)` al decodificar:
  - protocol v1 → encode_mode = 0 (joint-based)
  - protocol v2/v3 → encode_mode = 2 (SMPL-based)
- En motions desde CSV, `encode_mode` puede venir de metadata/config o se puede cambiar por input (teclas / lógica runtime).

