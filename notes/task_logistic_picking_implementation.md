# Task Implementation Plan — `LMLogisticsPicking`

**Propósito:** plan para implementar la task de simulación que materializa el Track 1 del WBCD 2026 (ver `Logistic_picking.md`) como un entorno RoboCasa drop-in del stack `decoupled_wbc/`, de modo que `run_sync_sim_data_collection.py task_name=LMLogisticsPicking` funcione exactamente igual que con `LMBottlePnP` o `LMPnPAppleToPlate` existentes.

**Este doc es plan, no código.** El código sale después, por fases.

**Integración con el playbook:** esta task corresponde a la **Fase 10** de `playbook_sim_logistics.md`. La Fase 8 (recolectar sobre `LMPnPAppleToPlate`) **es un pre-requisito** — valida el pipeline con una task conocida antes de introducir una task custom.

---

## 1. Mapeo reglamento → código

El Track 1 (`Logistic_picking.md`) pide 3 subtasks secuenciales: **pick → transport → place**, con 3 alturas de estante y 10 ítems. Eso se descompone en componentes RoboCasa así:

| Requisito reglamento | Componente RoboCasa | Patrón a replicar |
|---|---|---|
| Estante 3 niveles (top/middle/bottom) | `lab_shelf` asset + `ReferenceConfig(spawn_id=N)` | `PnPBottleShelfToTable` (`base.py:1235-1337`) |
| Ítem picable | `SceneObject` via `ObjectConfig` | `LMBottlePnP` (`locomanip_pnp.py:22-63`) |
| Mesa/carro de destino | `factory_ergo_table` o `lab_table` MJCF | `LMBottlePnP` |
| Criterio de éxito por altura (+5/+8/+10) | `AllCriteria` + `IsInContact` + flag de altura detectada en pickup | Extensión custom, pattern base en `success_criteria.py` |
| Penalty por drop (-3) | Telemetría post-hoc, no en success criterion | Episode metadata |
| Percepción onboard only | Cámara `robot0_oak_egoview` (ya definida en G1 robot XML) | Viene gratis del arena + robot |
| Navegación a estante | Locomoción ya la resuelve SONIC | No requiere código de task |

**Conclusión:** estructuralmente es una fusión de `PnPBottleShelfToTable` (estante → mesa) + `LMBottlePnP` (patrón factory) + múltiples ítems + 3 alturas etiquetables. No estamos inventando nada nuevo — estamos componiendo piezas existentes.

---

## 2. Decisión arquitectónica: de qué heredar

Tenemos dos niveles de abstracción:

- **Low-level (`base.py`):** override manual de `_load_model`, `_check_success`, `_load_objects`. Más control, más código. Ejemplo: `PnPBottleShelfToTable`.
- **High-level (`locomanip.py` LMEnvBase):** sistema declarativo de `Scene` con `_get_objects`, `_get_success_criteria`, `_get_instruction`. Más corto, más estándar. Ejemplo: `LMBottlePnP`, `LMPnPAppleToPlate`.

**Decisión:** usar el **high-level LMEnvBase pattern** (como `LMBottlePnP`). Razones:
1. Más corto y legible → menos superficie de bugs.
2. El `Scene` system ya maneja randomización de spawns (necesario para robustez del dataset).
3. El `_get_instruction()` nos da el label de lenguaje gratis (necesario para GR00T-N1.5).
4. Es el estándar reciente del repo — las tasks nuevas siguen este pattern.

**Cadena de herencia propuesta:**

```
LMEnvBase                                  (Scene system, 3 abstract methods)
  └─ LMWarehouseEnv (NEW)                  (sets MUJOCO_ARENA_CLS)
       └─ LMLogisticsPicking (NEW)         (objects + success + instruction)
```

**Sobre el arena** (`LMWarehouseEnv`): tenemos tres opciones:

| Opción | Pros | Contras |
|---|---|---|
| (a) Usar `LabArena` existente | 0 código adicional; ya está calibrado | Escena "laboratorio", no parece warehouse |
| (b) Usar `FactoryArena` existente | 0 código adicional; estética industrial | No trae shelving |
| (c) Crear `WarehouseArena` nuevo | Realista al Track 1 | +200 LOC + XML arena + texturas |

**Recomendación:** empezar con **(a) `LabArena`**. Para MVP y recolección de datos la estética no importa — lo que importa es el espacio, piso plano, iluminación. Si en Fase 11 (volumen) el generalización sufre por mismatch sim↔real, migramos a (c).

---

## 3. Estrategia de assets

### 3.1 Estante (3 niveles lógicos de los 6 físicos)

El asset `lab_shelf` tiene **6 niveles físicos** (z = 0.33, 0.59, 0.92, 1.22, 1.50, 1.81 m per `model.xml:19-66`). El reglamento pide **3 niveles lógicos** (upright/bent/crouched). Mapeo:

| Reglamento | Altura target (paper SONIC §2.2) | `spawn_id` de `lab_shelf` | Altura real |
|---|---|---|---|
| Top (upright, +5) | `base_height ≈ 0.74 m` | `spawn_id=4` | z ≈ 1.50 m |
| Middle (bent, +8) | `base_height ≈ 0.55 m` | `spawn_id=2` | z ≈ 0.92 m |
| Bottom (crouched, +10) | `base_height ≈ 0.35 m` | `spawn_id=0` | z ≈ 0.33 m |

Los `spawn_id` intermedios (1, 3, 5) quedan como "distractor levels" o como ítems secundarios que no se piden. La variación real viene del spawn dentro del nivel (randomización x,y).

### 3.2 Ítems — qué tenemos, qué falta

Inventario actual en `decoupled_wbc/dexmg/gr00trobocasa/robocasa/models/assets/objects/omniverse/locomanip/`:

| Ítem reglamento | Asset en repo | Estrategia MVP |
|---|---|---|
| Coke | ❌ | Proxy: `jug_a01` |
| Poker Cards | ❌ | Proxy: `longbox_a08` |
| Speed Cube | ✅ `rubix_cube_1` | Usar directo |
| Tennis Ball | ❌ | Proxy: esfera primitiva (MuJoCo builtin) |
| Cling Wrap | ❌ | Proxy: `cardbox_a1` pequeño |
| Soft Toy | ❌ | Proxy: `apple_0` |
| Bowl | ❌ | Proxy: `plate_1` escalado |
| Toilet Paper | ❌ | Proxy: cilindro primitivo |
| Bar Soap | ❌ | Proxy: `cardbox_a1` escalado |
| Potato Chips | ❌ | Proxy: `longbox_a09` |

**Fases de enriquecimiento:**
- **MVP (Fase 10.1):** 3 ítems reales (cubo Rubik + 2 proxies) para validar el pipeline.
- **V1 (Fase 10.3):** los 10 ítems con proxies geométricos (paralelepípedos/cilindros escalados a dimensiones reales del reglamento).
- **V2 (post-competencia si sobra tiempo):** meshes fotorrealistas importadas de Objaverse/MuJoCo Menagerie. No es requisito para ganar — GR00T N1.5 generaliza razonablemente a texturas sim↔real.

### 3.3 Mesa de carga

Reutilizar `factory_ergo_table` o `lab_table` (ya usadas en `LMBottlePnP`). Posicionamiento: a ~1.2 m del estante, perpendicular, suficiente para que el robot navegue.

---

## 4. Diseño del success criterion

El reglamento tiene **scoring granular** (+5/+8/+10 por altura, −3 por drop). En RoboCasa el `_check_success` devuelve boolean, no un score. Solución:

### 4.1 Éxito = "ítem sobre mesa de destino, upright"

```
AllCriteria(
    IsInContact(item, table_target),
    IsUpright(item),
    IsNotInContact(item, shelf)   # "ya fue removido del estante"
)
```

Con el mismo patrón que `LMBottlePnP:65-66`. El `IsNotInContact` hay que añadirlo (no existe, pero es trivial: inverso de `IsInContact`). Esto evita el falso positivo de "el ítem estaba ahí desde el inicio".

### 4.2 Scoring como metadata del episodio

El `+5/+8/+10` y el `−3 drop` **no son** éxito/fracaso — son **metadatos** de calidad. Se registran en el dataset, no en el criterion:

- **Al spawn:** guardar `spawned_shelf_level ∈ {top, middle, bottom}` en el episode info.
- **Al éxito:** guardar `pickup_posture` detectado (el robot puede fallar el +10 y resolverlo con +5 picando del shelf equivocado — queremos esa info).
- **Drops:** detectar contacto con el piso en el tramo de transporte. Añadir flag `had_drop: bool` a episode info.

Esto se hace en el exporter (custom callback) o en un `EpisodeMetadataMixin` nuevo, **no** en el task class. Mantiene la task limpia.

### 4.3 Instruction (label de lenguaje para GR00T)

```python
def _get_instruction(self) -> str:
    return f"pick the {self.item_name} from the {self.level_name} shelf and place it on the table"
```

Donde `item_name` y `level_name` se resuelven al reset. GR00T N1.5 condiciona sus chunks a este prompt — distribución amplia de prompts es oro para generalización.

---

## 5. Estructura de archivos propuesta

Todo en un archivo nuevo, siguiendo la convención del repo:

```
decoupled_wbc/dexmg/gr00trobocasa/robocasa/environments/locomanipulation/
  locomanip_logistics.py          ← NEW  (task class + arena mixin)
```

Reutilizando criterios existentes donde se pueda, o añadiendo al archivo de criterios:

```
decoupled_wbc/dexmg/gr00trobocasa/robocasa/environments/locomanipulation/
  success_criteria.py             ← posiblemente añadir IsNotInContact
```

No hay que tocar:
- `__init__.py` → los registros son automáticos vía `LocoManipulationEnvMeta` metaclass (`base.py:32-38`). Con que la clase se defina dentro del paquete, ya queda en `REGISTERED_LOCOMANIPULATION_ENVS`.
- `sync_env.py` → itera sobre el registry global, automático.
- `configs.py` → `task_name: str` ya es free-form.

**Resultado:** `task_name=LMLogisticsPicking` queda funcional tras el primer `import`.

---

## 6. Plan de implementación por fases

### Fase 10.1 — MVP (1-2 días)

**Objetivo:** demostrar que `task_name=LMLogisticsPicking` corre en el smoke test (`ci_test_mode=unit`, 50 steps, `body_control_device=dummy`).

Entregables:
1. `locomanip_logistics.py` con clase `LMLogisticsPicking(LMEnvBase)` minimal:
   - `LabArena` como arena (por ahora hardcoded, refactor a mixin en 10.2).
   - `lab_shelf` + `lab_table` + **1 ítem** (cubo Rubik `rubix_cube_1`, spawned en `spawn_id=0` fijo).
   - Success = `IsInContact(cube, table_target)`.
   - Instruction hardcoded: `"pick the cube from the shelf and place it on the table"`.
2. Smoke test passing:
   ```bash
   python decoupled_wbc/control/main/teleop/run_sync_sim_data_collection.py \
     task_name=LMLogisticsPicking body_control_device=dummy \
     ci_test=True ci_test_mode=unit enable_onscreen=True
   ```
3. Captura visual: ventana MuJoCo con G1 + estante + mesa + cubo.

**No incluye:** randomización, múltiples ítems, multi-altura, metadatos de scoring.

### Fase 10.2 — Randomización + 3 alturas (1 día)

**Objetivo:** cada reset samplea aleatoriamente (nivel, ítem, posición dentro del nivel). Esto es lo que necesita el dataset para ser diverso.

Entregables:
1. `LMWarehouseEnvMixin` extraído (MUJOCO_ARENA_CLS = LabArena).
2. 3 ítems reales/proxy: `rubix_cube_1`, `jug_a01` (proxy Coke), `apple_0` (proxy soft toy).
3. Sampler: cada episodio elige `level ∈ {top, middle, bottom}` y `item ∈ {3 ítems}`. Spawn al nivel correspondiente.
4. `level_name` y `item_name` expuestos como `self.level_name`, `self.item_name` para `_get_instruction()`.
5. Test: correr 10 episodios dummy y confirmar varianza (log de instrucciones generadas).

### Fase 10.3 — 10 ítems con proxies + metadatos de scoring (2-3 días)

**Objetivo:** cobertura completa del reglamento y dataset etiquetado con `posture_score` y `had_drop`.

Entregables:
1. Wrap de los 10 ítems del reglamento como `ObjectConfig` (proxies geométricos donde falten meshes).
2. Callback `EpisodeMetadataWriter` que añade al `episode.info`:
   - `spawned_shelf_level: str`
   - `spawned_item: str`
   - `pickup_posture: str` (detectado del `base_height` del G1 en el frame del grasp)
   - `had_drop: bool`
   - `posture_score: int` (+5/+8/+10)
   - `final_score: int` (posture_score − 3 × drops)
3. Success criterion refinado: `AllCriteria(IsInContact(item, table), IsUpright(item), IsNotInContact(item, shelf))`.
4. Test: 20 episodios dummy, verificar distribución de metadatos en el dataset exportado.

### Fase 10.4 — Validación manual con PICO (0.5-1 día)

**Objetivo:** grabar 5-10 trayectorias reales teleoperadas para cerrar el loop y detectar problemas de UX (cámara, distancias, obstáculos no previstos).

Ajustes esperados tras este paso:
- Reposicionar estante si el G1 no llega cómodamente al top shelf.
- Reposicionar mesa si choca con el estante.
- Ajustar rangos de `spawn_id` si algún nivel es inalcanzable físicamente.

---

## 7. Criterios de aceptación de la task

Antes de pasar a Fase 11 (volumen), la task debe cumplir:

1. ✅ Se resuelve por nombre (`task_name=LMLogisticsPicking` funciona).
2. ✅ Smoke test (`ci_test_mode=unit`) pasa sin errores.
3. ✅ Se graban episodios en formato LeRobot con las 9 claves del action dict que produce el teleop (`left_wrist_eef_9d`, `right_wrist_eef_9d`, `left_hand`, `right_hand`, `left_arm`, `right_arm`, `waist`, `base_height_command`, `navigate_command`).
4. ✅ Cada episodio trae los metadatos: `spawned_shelf_level`, `spawned_item`, `pickup_posture`, `had_drop`, `posture_score`.
5. ✅ El `ego_view` de la cámara onboard muestra el estante y el ítem cuando el G1 está frente a la escena (validar manualmente).
6. ✅ El playback del episodio (`playback_sync_sim_data.py`) reproduce la trayectoria sin caídas.
7. ✅ 5+ episodios teleoperados reales validan la UX antes de escalar a volumen.

---

## 8. Riesgos técnicos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| `lab_shelf` demasiado alto — G1 no alcanza top shelf | Media | Primero validar alturas con Fase 5 (walk + teclado `1`/`2`). Si es inviable, bajar `spawn_id` del top. |
| SONIC pierde estabilidad en crouched profundo | Baja | SONIC soporta 0.3-0.8 m pelvis (paper §2.2); crouched pickup ≈ 0.35 m está en rango. |
| Proxies de ítems generan dinámicas irreales (fricción, masa) | Media | Calibrar masa/fricción vs. ítem real en Fase 10.3. El paper muestra que GR00T generaliza razonablemente a mismatches moderados. |
| `IsNotInContact` no se puede implementar sin colisiones fantasma | Baja | Fallback: `IsPositionInRange(item_z, shelf_top_z + 0.3)` ("ítem levantado claramente"). |
| Metadatos de scoring ralentizan la grabación | Baja | El callback solo corre en `reset` y `check_success`, no por frame. |

---

## 9. Qué **no** haremos en esta task (anti-scope)

- **No** implementamos el scoring oficial de 10 minutos acumulado. Eso es lógica de competencia, no de entorno. Se calcula offline con los metadatos.
- **No** diseñamos el controlador óptimo para múltiples ítems por trip. Eso es política del VLA, no del env.
- **No** simulamos el reglamento completo (timer, árbitros, penalty tracking). Un episodio = una picking sequence. La acumulación la ve GR00T durante entrenamiento con episodios variados.
- **No** creamos `WarehouseArena` custom. Usamos `LabArena` y revisamos en V2.
- **No** integramos physics de cling wrap deformable (es tela, MuJoCo no lo simula bien sin add-ons). Se trata como rígido.

---

## 10. Dependencias externas del plan

Antes de arrancar Fase 10.1, todo lo siguiente debe estar verde:

- [ ] Playbook Fase 4 (`install_ros.sh`) completo → `rclpy` importable.
- [ ] Playbook Fase 6 (`task_name=PnPBottle` ci_test) passing.
- [ ] Playbook Fase 8 (recolección con PICO sobre `LMPnPAppleToPlate`) ≥ 1 episodio grabado y playback OK.
- [ ] Conocimiento en mano: haber leído `locomanip_basic.py:658-732` (`LMPnPAppleToPlate`), `locomanip_pnp.py:19-70` (`LMBottlePnP`), `base.py:1235-1337` (`PnPBottleShelfToTable`).

Las primeras 3 son las Fases anteriores del playbook. La última es literalmente 30 min de lectura.

---

## 11. Estado de este plan

- **Redactado:** 2026-04-21.
- **Implementación:** pendiente (bloqueada por Fases 4-9 del playbook).
- **Siguiente action:** cuando el usuario esté en Fase 10 del playbook, pedir el esqueleto del archivo `locomanip_logistics.py` aquí para arrancar Fase 10.1.
