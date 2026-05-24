# Real Robot Data Recording With PICO USB

Ultima modificacion: 2026-05-23 23:31:20 -05 -0500

Esta guia deja listo el flujo para probar en robot real con el PICO conectado a
la laptop por USB/ADB. El flujo real todavia no fue probado en el robot; queda
como smoke test para la siguiente sesion.

## Topologia

```text
PICO XRoboToolkit
  -> USB-C / ADB
  -> laptop: XRoboToolkit PC Service + pico_manager_thread_server.py

Robot / Unitree computer
  -> camera server con ego_view y opcional left_wrist/right_wrist
  -> ethernet
  -> laptop: data exporter + camera viewer + PICO video bridge

Laptop
  -> launch_data_collection.py
  -> C++ deploy real
  -> PICO manager
  -> data exporter
  -> camera viewer
```

La IP del robot solo se usa en la laptop con `--camera-host <ROBOT_IP>`.
Dentro del PICO, para este flujo USB, usa `127.0.0.1`.

## Antes De Probar

En el robot, levanta el camera server. Ejemplo con solo camara de cabeza/top:

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl
source .venv_camera/bin/activate

python -m gear_sonic.camera.composed_camera \
  --ego-view-camera usb \
  --ego-view-device-id <HEAD_CAMERA_ID> \
  --port 5555
```

Ejemplo con cabeza/top + ambas wrist cameras:

```bash
python -m gear_sonic.camera.composed_camera \
  --ego-view-camera usb \
  --ego-view-device-id <HEAD_CAMERA_ID> \
  --left-wrist-camera usb \
  --left-wrist-device-id <LEFT_WRIST_CAMERA_ID> \
  --right-wrist-camera usb \
  --right-wrist-device-id <RIGHT_WRIST_CAMERA_ID> \
  --port 5555
```

En la laptop, verifica que ves el PICO por USB:

```bash
adb devices
```

Y verifica que la laptop ve la camara del robot:

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl
source .venv_data_collection/bin/activate

python gear_sonic/scripts/run_camera_viewer.py \
  --camera-host <ROBOT_IP> \
  --camera-port 5555
```

## Que Configura El Launcher

Con `--pico-transport usb`, el launcher configura:

```bash
adb reverse tcp:63901 tcp:63901
```

Eso permite que XRoboToolkit en el PICO use:

```text
PC Service: 127.0.0.1
```

Si ademas usas `--pico-vision`, el launcher configura:

```bash
adb forward tcp:12345 tcp:12345
```

Entonces Remote Vision en el PICO debe usar:

```text
Remote Vision: ZEDMINI
Camera/source IP: 127.0.0.1
stream port: 12345
```

No uses la IP del robot dentro del PICO. El robot publica camaras hacia la
laptop por ethernet; la laptop reenvia la camara de cabeza/top al PICO por USB.

## Comando 1: Solo Cabeza/Top

Este comando graba solo `ego_view` en el dataset y tambien muestra solo
`ego_view` en el PICO:

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl
tmux kill-session -t sonic_data_collection 2>/dev/null || true

python gear_sonic/scripts/launch_data_collection.py \
  --pico-transport usb \
  --pico-vision \
  --pico-vision-camera-key ego_view \
  --camera-host <ROBOT_IP> \
  --camera-port 5555 \
  --wrist-cameras none \
  --task-prompt "real shelf manipulation" \
  --dataset-name "real_usb_head_episode"
```

## Comando 2: Dataset Con Wrists, PICO Solo Cabeza/Top

Este comando graba `ego_view`, `left_wrist` y `right_wrist` en el dataset, pero
el PICO sigue mostrando solo `ego_view`:

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl
tmux kill-session -t sonic_data_collection 2>/dev/null || true

python gear_sonic/scripts/launch_data_collection.py \
  --pico-transport usb \
  --pico-vision \
  --pico-vision-camera-key ego_view \
  --camera-host <ROBOT_IP> \
  --camera-port 5555 \
  --wrist-cameras both \
  --task-prompt "real shelf manipulation" \
  --dataset-name "real_usb_head_wrist_episode"
```

Si solo tienes una wrist camera publicada por el robot, cambia `--wrist-cameras
both` por `--wrist-cameras left` o `--wrist-cameras right`.

## Checks Durante La Prueba

Despues de lanzar el comando, en otra terminal puedes revisar:

```bash
adb reverse --list
adb forward --list
```

Esperado con `--pico-vision`:

```text
tcp:63901 tcp:63901
tcp:12345 tcp:12345
```

En XRoboToolkit:

```text
Network / PC Service: WORKING
Remote Vision: debe mostrar la camara ego_view de cabeza/top
```

Si no hay video en el PICO, primero verifica que el camera viewer en la laptop
si reciba imagen desde `<ROBOT_IP>:5555`. Si el viewer no recibe imagen, el
problema esta en el camera server, la IP del robot, ethernet o las camaras.
