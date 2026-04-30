## SMPL encoder direct: dos caminos para reemplazar el VR (≤132 dims)

Este doc resume **qué señales necesita el pipeline** para el modo whole-body (“SMPL”), y documenta **dos rutas** para reemplazar el VR:

- **Ruta 1 (Encoder+Decoder intactos)**: tu NN predice un **vector por frame** (84D/88D) y tú mismo haces el **stack de 10 frames** para alimentar el encoder SMPL existente.
- **Ruta 2 (Bypass encoder)**: tu NN predice directamente el **`token_state` (64D)** y el deployment C++ salta el encoder usando **ZMQ protocol v4**.

---

### Contexto: qué consume el modo SMPL hoy

En `gear_sonic_deploy/policy/release/observation_config.yaml`, el encoder tiene modos, y para `mode_id=2` (**`smpl`**) declara como `required_observations`:

- `encoder_mode_4`
- `smpl_joints_10frame_step1`
- `smpl_anchor_orientation_10frame_step1`
- `motion_joint_positions_wrists_10frame_step1`

Esto coincide con el “single source of truth” en C++ (observation registry) en:

- `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/src/g1_deploy_onnx_ref.cpp` (`GetObservationRegistry()`)

En ese registry se ve explícitamente:

- `smpl_joints` = 72D por frame (24×3)
- `smpl_anchor_orientation` = 6D por frame (rotación 6D)
- `motion_joint_positions_wrists` = 6D por frame (6 DOFs de muñecas)
- y sus variantes `_10frame_step1` (concatenación de 10 frames)

---

## Ruta 1 — Predecir “84D por frame” y stackear a 10 (usar encoder SMPL existente)

### 1) Qué predice tu NN por frame (lo mínimo)

Si tu objetivo es “reconstruir” exactamente el input del encoder SMPL existente, lo mínimo por frame es:

- **`smpl_joints` (72D)**: 24 joints × xyz (en el mismo frame/convención que espera el deployment)
- **`smpl_anchor_orientation` (6D)**: orientación del anchor/pelvis en 6D (misma convención que `GatherMotionAnchorOrientationMutiFrame`)
- **`motion_joint_positions_wrists` (6D)**: 6 joints de muñeca del robot (wrist roll/pitch/yaw por lado)
- **`encoder_mode_4` (4D)**: one-hot del modo (para SMPL típicamente “smpl”)

Dimensión:

- **84D** = 72 + 6 + 6 (sin contar el modo)
- **88D** = 72 + 6 + 6 + 4 (incluyendo `encoder_mode_4`)

### 2) Qué construyes con un buffer de 10 frames

Mantienes un buffer FIFO de longitud 10 (context window) y construyes:

- `smpl_joints_10frame_step1`: shape (10,24,3) → 720D
- `smpl_anchor_orientation_10frame_step1`: shape (10,6) → 60D
- `motion_joint_positions_wrists_10frame_step1`: shape (10,6) → 60D
- `encoder_mode_4`: shape (4,) → 4D

Eso es **exactamente** lo que pide el encoder SMPL en `observation_config.yaml`.

### 3) ¿Es suficiente para “controlar” whole-body usando el encoder+decoder tal cual?

**Sí**, con esta condición:

- Debes alimentar al encoder SMPL los tensores con **la misma convención** (frames, signos, ejes, 6D rotation flattening) que espera el deployment.

El decoder además siempre usa las “observaciones base” (IMU, joints del robot, historia), pero eso viene del robot/state logger: **no lo tienes que predecir**.

### 4) Nota crítica si tu inyección es “por ZMQ como si fuera VR”

Si inyectas por ZMQ usando los protocolos “motion” (v2/v3), el receptor C++ suele validar campos requeridos del mensaje (por ejemplo `smpl_pose` puede ser requerido por el protocolo aunque el encoder SMPL no lo use). En ese caso, tienes dos alternativas:

- **A)** Enviar también los campos extra requeridos por el protocolo ZMQ de motion (aunque el encoder no los consuma), o
- **B)** No usar ZMQ-motion para esto, y en su lugar usar la Ruta 2 (tokens) o extender el sender/C++ para aceptar un “SMPL-minimal protocol”.

---

## Ruta 2 — Bypass del encoder: tu NN predice `token_state` (64D) (ZMQ protocol v4)

Esta ruta evita por completo predecir SMPL joints/anchor/wrists.

### 1) Qué predice tu NN

- **`token_state`**: un vector de **64 floats** (o lo que diga `encoder.dimension` en el config).

Esto cumple perfecto tu límite ≤132D y es la ruta más simple para “reemplazar el VR”.

### 2) Dónde está implementado en C++

Está soportado explícitamente:

- `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/include/input_interface/zmq_endpoint_interface.hpp`
  - **Protocol v4**: token-only streaming (`token_state` requerido).
- `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/src/g1_deploy_onnx_ref.cpp`
  - `GatherInputInterfaceData()`:
    - copia tokens externos → `token_state_data_`
    - fuerza `is_using_encoder_ = false`
  - `GatherTokenState()`:
    - inserta `token_state_data_` al vector de observación del policy.

### 3) Formato del mensaje ZMQ (protocol v4)

- **header**: `v: 4`
- **field requerido**:
  - `token_state`: dtype `f32` o `f64`, shape `[64]` (o `[1,64]`)
- **fields opcionales**:
  - `frame_index` (debug/log)
  - `left_hand_joints`, `right_hand_joints` (7 DOF por mano, si también quieres controlar mano)
  - `body_quat_w` (opcional; **no requerido** en v4)

### 4) ¿Es suficiente para teleoperar whole-body?

**Sí**, porque el decoder está diseñado para mapear:

\[
(\text{base\_obs del robot}) \;\oplus\; (\text{token\_state 64D})
\;\rightarrow\; \text{comandos de 29 DOFs}
\]

En SMPL original, el VR/SMPL solo existe para construir ese `token_state` a través del encoder. Aquí tu NN reemplaza ese “bloque humano→token”.

---

## Resumen rápido: cuál ruta usar

- Si quieres que tu NN “reemplace el VR” pero **sin cambiar el deployment** y con el máximo de compatibilidad: **Ruta 2 (token v4)**.
- Si quieres que tu NN aprenda explícitamente “representación física tipo SMPL” y seguir usando el encoder SMPL existente: **Ruta 1**, pero te exige **convenciones exactas** y (si vas por ZMQ-motion) respetar los **campos requeridos del protocolo** aunque el encoder no los use.

