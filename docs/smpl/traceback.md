# Resumen completo: variables para inferencia en modo `smpl`

## Lo que ya tienes computado (de `traceback.md`)

Estas son exactamente las 4 observaciones del encoder para el modo `smpl`:

| Variable | Dim | Cómo se computa |
|---|---|---|
| `encoder_mode_4` | 4D | Interno: el deploy lo fija en `[2, 0, 0, 0]` al recibir protocolo v2/v3 |
| `smpl_joints_10frame_step1` | 720D (24×3×10) | SMPL forward pass en Python: posiciones 3D de 24 joints en frame local del pelvis |
| `smpl_anchor_orientation_10frame_step1` | 60D (6D×10) | `body_quat` del stream + `base_quat` del robot → rotación relativa 6D |
| `motion_joint_positions_wrists_10frame_step1` | 60D (6 joints×10) | `joint_pos` del stream → 6 articulaciones de muñeca (wrist roll/pitch/yaw ×2) |

---

## Lo que falta — Policy (viene del robot físico)

Las observaciones del **policy** (no del encoder) usan el historial real del robot vía `StateLogger`. Estas **no vienen del Pico** ni se pueden precomputar:

| Variable YAML | Dim | Dato en `StateLogger` | Sensor físico |
|---|---|---|---|
| `his_base_angular_velocity_10frame_step1` | 30D (3×10) | `base_ang_vel` | Giroscopio pelvis (`imu_state().gyroscope()`) |
| `his_body_joint_positions_10frame_step1` | 290D (29×10) | `body_q` | Encoders 29 motores (`motor_state[i].q()`) |
| `his_body_joint_velocities_10frame_step1` | 290D (29×10) | `body_dq` | Encoders 29 motores (`motor_state[i].dq()`) |
| `his_last_actions_10frame_step1` | 290D (29×10) | `last_action` | Interno: acción que generó la policy en el tick anterior |
| `his_gravity_dir_10frame_step1` | 30D (3×10) | `base_quat` → rota `[0,0,-1]` | IMU pelvis (`imu_state().quaternion()`) |

Nota: `smpl_anchor_orientation_10frame_step1` también **necesita** `base_quat` del robot en tiempo real para calcular la orientación relativa.

---

## Lo que falta — ZMQ protocolo (requerimiento de red, no del encoder)

Para que el mensaje ZMQ sea aceptado como v2 sin ser rechazado por el decoder C++:

| Campo ZMQ | Requerido para | Origen |
|---|---|---|
| `body_quat` `[N×4]` | Protocolo v2 obligatorio; base para `smpl_anchor_orientation` | Pico → Python |
| `smpl_pose` `[N×21×3]` | **Protocolo v2 obligatorio** (ver sección siguiente) | Pico → Python |
| `frame_index` `[N]` | Sincronización del sliding window | Pico / contador propio |
| `joint_pos` `[N×29]` | Requerido para `motion_joint_positions_wrists_*` | Pico → Python |

---

## `smpl_pose` vs `smpl_joints` — diferencia y uso real

**Son representaciones totalmente distintas:**

| | `smpl_joints` | `smpl_pose` |
|---|---|---|
| **Qué representa** | **Posiciones 3D** de 24 joints (salida de FK) | **Rotaciones axis-angle** de 21 joints (entrada del modelo SMPL) |
| **Dimensión** | `[N, 24, 3]` = 72D/frame | `[N, 21, 3]` = 63D/frame |
| **Analogía** | Dónde está cada articulación en el espacio | Cuánto está rotada cada articulación |
| **Se usa como observación del encoder?** | **Sí** — `smpl_joints_10frame_step1` está en `required_observations` del modo `smpl` | **No** — no está en ningún `encoder_observations` del YAML activo |
| **Se usa en el C++?** | Sí, `GatherMotionSmplJointsMultiFrame` → buffer del encoder | Existe en el registro (`GatherMotionSmplPosesMultiFrame`) pero **ninguna observación activa lo llama** |
| **Por qué va en el mensaje ZMQ?** | Dato de observación | El protocolo v2 lo exige para validar el mensaje (`zmq_endpoint_interface.hpp`); si falta, el mensaje se rechaza |

**En resumen: `smpl_pose` no alimenta ninguna observación de la red, pero debes enviarlo en el mensaje ZMQ o el C++ rechaza el paquete entero.**

Referencias de código:

- `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/include/input_interface/zmq_endpoint_interface.hpp` — validación protocolo v2/v3: `smpl_joints` y `smpl_pose` obligatorios.
- `gear_sonic_deploy/src/g1/g1_deploy_onnx_ref/src/g1_deploy_onnx_ref.cpp` — registro de observaciones: `smpl_joints_*` vs `smpl_pose_*`.
- `gear_sonic_deploy/policy/release/observation_config.yaml` — modo `smpl`: solo `encoder_mode_4`, `smpl_joints_10frame_step1`, `smpl_anchor_orientation_10frame_step1`, `motion_joint_positions_wrists_10frame_step1`.

---

## Diagrama global

```
┌─────────────────────────────────────────────────────────────┐
│                    YA TIENES COMPUTADO                       │
│  encoder_mode_4 · smpl_joints_10f · smpl_anchor_ori_10f     │
│  motion_joint_positions_wrists_10f                          │
└─────────────────┬───────────────────────────────────────────┘
                  │ (encoder ONNX) → token_state [64D]
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    POLICY ONNX (436D total)                  │
│  token_state [64]                                           │
│  + his_base_angular_velocity_10f [30]  ← giroscopio robot   │
│  + his_body_joint_positions_10f  [290] ← encoders robot     │
│  + his_body_joint_velocities_10f [290] ← encoders robot     │
│  + his_last_actions_10f          [290] ← acción previa      │
│  + his_gravity_dir_10f           [30]  ← IMU pelvis robot   │
└─────────────────────────────────────────────────────────────┘

EXTRA para que el mensaje ZMQ sea válido (no son observaciones):
  body_quat [N×4] · smpl_pose [N×21×3] · frame_index [N]
```

---

## Origen de datos (resumen por fuente)

**Robot físico (Unitree G1):** `base_quat`, `base_ang_vel`, `body_q`, `body_dq` (y derivados `his_*`, gravedad, parte de anchor).

**PC externa (Pico → Python → ZMQ):** `smpl_joints`, `joint_pos`, `body_quat`, `smpl_pose`, `frame_index`.

**Interno al deploy C++:** `encoder_mode_4` (modo fijado por protocolo), `last_action` (tick anterior de la policy).
