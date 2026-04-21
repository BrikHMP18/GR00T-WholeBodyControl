# Pipeline: Ganar WBCD 2026 Track 1 (Logistics Picking) con GR00T + SONIC

Este documento especifica cómo combinar el **VLA GR00T N1.5** (razonamiento deliberativo / System 2) con el **controlador universal SONIC** (tracking whole-body reactivo / System 1) para resolver el Track 1 — Logistics Picking del WBCD 2026 con la plataforma que ya vive en este repo (`decoupled_wbc/` + `gear_sonic/`).

La arquitectura está basada en la demostración del paper SONIC §2.4.3 (apple-to-plate, 95 % success en 20 trials) escalada a una distribución de tareas más rica, que el propio paper señala explícitamente como future work.

---

## 1. Mapa tarea ↔ capacidades

| Requisito del Track 1 | Capacidad SONIC/GR00T que lo resuelve | Referencia paper / repo |
|---|---|---|
| 10 min, sin límite de ítems por ciclo | GR00T planifica secuencia; tiempo de ciclo dominado por locomoción y agarre | — |
| **1a Top shelf / Upright** (+5) | `base_height_command ≈ 0.74 m` + alcance bimanual a altura pecho/hombro | SONIC §2.2 (pelvis 0.3–0.8 m) |
| **1b Middle shelf / Bent** (+8) | `base_height_command ≈ 0.5–0.6 m`, ligero pitch de cintura | idem |
| **1c Bottom shelf / Crouched** (+10) | `base_height_command ≈ 0.3–0.35 m`, squat whole-body | idem (squat + kneel already supported) |
| Step 2 Transportation (penaliza drop -3) | Universal tracker + slow-walk locomotion mode | SONIC §2.4.2 (locomotion mode slow/fast) |
| Step 3 Placement estable | Bimanual wrist-pose control en token universal | SONIC §2.4.3 |
| **Percepción sólo onboard** | GR00T condiciona sus tokens de acción a las cámaras del G1 (head-mounted). SONIC es propioceptivo — no necesita visión externa. | Regla WBCD + arquitectura GR00T N1.5 |
| VR / mocap permitidos **para teleop de colección** | PICO 3-point teleop (head + 2 controllers, sin ankle trackers) | SONIC §2.4.2, `decoupled_wbc/control/teleop/` |

**Conclusión del mapa:** cada posture-bonus (+5/+8/+10) se reduce a elegir un `base_height_command` diferente antes de mandar la pose de muñecas. No hay que reentrenar SONIC; ya cubre ese rango de altura de pelvis.

---

## 2. Arquitectura runtime

```
                 ┌─────────── onboard cameras (G1 head) ──────────┐
                 │                                                │
                 ▼                                                │
     ┌────────────────────────┐       Token universal             │
     │   GR00T N1.5 (VLA)     │  (mismo formato que 3-point       │
     │   fine-tuned on WBCD   │   teleop: head+2 wrists SE(3),    │
     │   logistics data       │   finger joints, base_height,     │
     └────────────┬───────────┘   locomotion_mode, nav_cmd)       │
                  │                                               │
                  ▼                                               │
     ┌────────────────────────┐                                   │
     │ Kinematic Planner      │  (SONIC §3.3, <5 ms CPU /         │
     │ + Hybrid Encoder (Em)  │   <12 ms Jetson Orin)             │
     └────────────┬───────────┘                                   │
                  │ universal token z                             │
                  ▼                                               │
     ┌────────────────────────┐                                   │
     │ SONIC control decoder  │  (universal control policy)       │
     │  Dc → motor targets    │                                   │
     └────────────┬───────────┘                                   │
                  ▼                                               │
     ┌────────────────────────┐     proprio feedback ─────────────┘
     │ PD @ 50 Hz → Unitree G1│
     └────────────────────────┘
```

**System 2 (GR00T)** corre al ritmo de planificación (~20–30 Hz chunks de horizonte 40 — el dict de acción que ya observamos en el repo, `shape=(1, 40, 9)` para `*_eef_9d`).
**System 1 (SONIC)** corre el control PD a 50 Hz, absorbiendo perturbaciones y el 121.9 ms de latencia medido del lazo 3-point.

### Puntos de engarce en el código existente

- Entrada a SONIC: `decoupled_wbc/control/policy/g1_gear_wbc_policy.py:175-241` (`set_goal(nav_cmd, base_height, torso_rpy)` + obs propriocep).
- Contrato del action dict que el WBC consume: `decoupled_wbc/control/policy/lerobot_replay_policy.py:49-85` (**usar como plantilla** para un nuevo `gr00t_policy.py`).
- Features del espacio VLA: `gear_sonic/.../features_sonic_vla.py` (`vr_3pt_position` 9D, `vr_3pt_orientation` 18D rotation_6d — ya es exactamente el formato que saldrá del VLA).
- Pipeline de recolección: `decoupled_wbc/control/main/teleop/run_teleop_policy_loop.py`, `run_sync_sim_data_collection.py`.

---

## 3. Plan de ejecución por fases

### Fase 0 — Verificación (1–2 días)

1. Levantar el teleop PICO con `bash install_scripts/install_pico.sh` y correr `run_teleop_policy_loop.py` en simulación.
2. Confirmar que `lerobot_replay_policy` reproduce una trayectoria grabada sobre SONIC sin caídas.
3. Grep final por `gr00t`, `n1_5`, `vla` en el repo para saber si el **connector GR00T→token universal ya está commiteado**. Si no existe, la Fase 3 incluye construirlo replicando `lerobot_replay_policy` pero con inferencia de GR00T en lugar de lectura de disco.

**Salida:** confirmación de que SONIC + teleop + replay es funcional end-to-end.

### Fase 1 — Setup de la arena y el robot

- Montar estantería con 3 niveles de altura aproximados: top ≈ 1.3 m, middle ≈ 0.9 m, bottom ≈ 0.3 m (ajustar al reglamento final).
- Mesa de carga al lado.
- G1 con efector final elegido: recomendado **dex-hand de 3 dedos** para el mix de ítems (Coke, Bowl, Toilet Paper, Cling Wrap, Bar Soap) — las pinzas simples fallan en objetos blandos/deformables.
- Calibrar cámaras del head-mount del G1 (único sensor externo permitido por reglamento).

### Fase 2 — Recolección de datos por teleop PICO (3-point)

**Objetivo de dataset:** ~1500–2000 trayectorias (5–7× las 300 del PoC apple, dado que la distribución es más ancha).

Distribución objetivo por altura × ítem × posición en estante:

| Posture | Trayectorias objetivo | Razón |
|---|---|---|
| 1c Crouched (+10) | ~40 % del dataset | Más puntos, más riesgo, más varianza postural |
| 1b Bent (+8) | ~35 % | Bonus medio, postura menos practicada en mocap |
| 1a Upright (+5) | ~25 % | El más fácil; suficiente con menos datos |

**Por cada ítem (10 ítems × 3 alturas = 30 bins):**
- ≥ 50 tomas con variaciones de posición del ítem en la balda, del estante relativo al robot, y de iluminación.
- Incluir negativos suaves: vecinos en la balda cerca del objetivo para enseñar a no tumbarlos.
- Transporte: grabar también el tramo locomoción + placement como parte de la misma trayectoria (el VLA aprende la tarea completa, no trozos).

**Comando a usar:** `run_sync_sim_data_collection.py` con el stream del PICO. La grabación debe capturar:

- Observación: frames RGB de las cámaras onboard del G1 + propriocep.
- Acción (token universal, ya producido por el teleop): head SE(3), L-wrist SE(3), R-wrist SE(3), finger joints L/R, `base_height_command`, `locomotion_mode ∈ {slow_walk, fast_walk}`, `navigate_cmd` (vx, vy, wz).
- Etiquetas de lenguaje: prompt textual por trayectoria del tipo `"pick the <item> from the <top|middle|bottom> shelf and place it on the table"` — GR00T N1.5 es un VLA, no desperdiciemos el canal de lenguaje.

### Fase 3 — Fine-tuning de GR00T N1.5

- Base: checkpoint público `gr00t-n1.5` (NVIDIA).
- Action head configurado al token universal (~40D: 2×wrist 9D + 7D finger L + 7D finger R + base_height 1D + locomotion_mode 1D + nav_cmd 3D + head 9D). Este header ya está definido en `features_sonic_vla.py`.
- Observación: cámaras onboard del G1 + propriocep (mismas features que el teleop usó durante recolección — evitar cambio de distribución entre entrenamiento y despliegue).
- Predicción en chunks (ya vimos `horizon = 40` pasos en el runtime del repo).
- Aumentación: random-mask de un stream de cámara, pequeñas perturbaciones de `base_height` y `nav_cmd` para robustez.
- Métrica de validación offline: MSE del token universal vs. trayectoria ground-truth + criterio de éxito en replay simulado sobre SONIC en Isaac Lab.

**Criterio de pasar a real:** ≥ 90 % success en sim sobre un holdout de 50 configuraciones aleatorias de estante/ítem antes de despliegue real.

### Fase 4 — Integración runtime

Crear `decoupled_wbc/control/policy/gr00t_policy.py` replicando la interfaz de `lerobot_replay_policy.py:49-85` pero sustituyendo la lectura de disco por inferencia de GR00T:

- `get_action(obs)` → runs GR00T forward con obs de cámaras + propriocep → devuelve dict `{wrist_pose, navigate_cmd, base_height_cmd, target_upper_body_pose, …}` como espera el WBC.
- Alimentar ese dict al pipeline existente `kinematic_planner + hybrid_encoder + universal_control_policy`.
- Policy toggle vía PICO button (heredado del teleop) — permite tomar control manual si el VLA se atasca. Útil en la competencia si un estante se desordena.

### Fase 5 — Estrategia competitiva

Scoring objetivo: **maximizar puntos/minuto**, no ítems/minuto.

- **Orden sugerido por ciclo de 10 min:** priorizar bottom (+10) y middle (+8) porque el costo en tiempo de un ciclo crouched no es 2× el upright (el tracker de SONIC es rápido en transiciones de altura; la transición squat↔stand añade ~1–1.5 s).
- Capacidad de ítems por trip: llevar 2–3 ítems simultáneos si el efector lo permite. Un drop cuesta −3 → cada trip multi-ítem tiene que tener P(drop) < 0.2 para ser rentable. Evaluar en Fase 4.
- Uso de `locomotion_mode = slow_walk` durante transporte con carga. `fast_walk` sólo vacío, camino al estante.
- **Golden loop:** 1 ciclo ≈ {navegar → bottom-pick (2 ítems) → slow-walk a mesa → place → fast-walk a estante → middle-pick → slow-walk → place}. Calcular tiempo medio por ciclo y dimensionar sobre 10 min.

---

## 4. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Connector GR00T↔token universal no está en este repo | Bloquea Fase 4 | Construirlo en Fase 0 con `lerobot_replay_policy` como plantilla — es un wrapper, no un cambio a SONIC |
| GR00T no generaliza a los 10 ítems con sólo 1500 trayectorias | Baja performance real | Priorizar volumen en ítems más difíciles (cling wrap, toilet paper, soft toy); usar lenguaje para condicionar por ítem |
| Drops durante transporte (−3 c/u) | Pierdes puntos de alto valor | Entrenamiento específico de "stabilize during locomotion"; limitar a 1 ítem/trip hasta validar P(drop) en sim |
| Occlusion en bottom shelf por postura crouched | VLA no ve el ítem | Grabar Fase 2 con pre-poses (el robot mira antes de crouchear); GR00T aprende el pre-gaze |
| Latencia acumulada VLA (~50 ms) + tracker (~122 ms) | 170 ms end-to-end | El kinematic planner ya interpola — es tolerable; si no, ejecutar GR00T en Jetson Orin a 30 Hz con chunk-forward |
| Cambio de distribución sim↔real | Falla en competencia | Últimos 20 % del dataset grabarlos **en el robot real** y hacer un re-fine-tune corto antes del evento |
| Reglamento: "onboard perception only" | Descalifica si usas mocap externo en runtime | PICO **sólo** se usa en Fase 2 (recolección). En runtime sólo cámaras head del G1. GR00T no ve el PICO. |

---

## 5. Entregables mínimos antes de competir

1. Dataset de ≥ 1500 trayectorias teleoperadas con labels de lenguaje y distribución 25/35/40 (upright/bent/crouched).
2. Checkpoint fine-tuned de GR00T N1.5 con ≥ 90 % success en sim holdout.
3. `gr00t_policy.py` integrado con SONIC, validado en el G1 real.
4. Playbook de competencia: orden de ciclos, política de multi-ítem, y protocolo de toma de control manual vía PICO.

---

## 6. Resumen en una frase

SONIC ya provee el System 1 whole-body que sabe pararse, agacharse, caminar y tracker muñecas; GR00T N1.5 aporta el System 2 que decide *qué* muñecas y *qué* altura de pelvis usar en cada momento — nuestro trabajo es recolectar las trayectorias teleoperadas para el Track 1 en el token universal de SONIC, finetuneaR GR00T en ellas y conectar el action dict al pipeline WBC existente.
