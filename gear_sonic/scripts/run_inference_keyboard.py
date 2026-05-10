"""Tiny ZMQ keyboard publisher for SONIC inference/data-collection controls."""

from dataclasses import dataclass
import time

import tyro
import zmq

from gear_sonic.utils.data_collection.keyboard_subscriber import (
    DEFAULT_ZMQ_KEYBOARD_PORT,
)


@dataclass
class InferenceKeyboardConfig:
    """CLI config for the keyboard publisher."""

    host: str = "localhost"
    """Host/interface to bind."""

    port: int = DEFAULT_ZMQ_KEYBOARD_PORT
    """ZMQ port consumed by run_vla_inference.py."""


def main(config: InferenceKeyboardConfig):
    ctx = zmq.Context()
    socket = ctx.socket(zmq.PUB)
    socket.bind(f"tcp://{config.host}:{config.port}")
    time.sleep(0.5)

    print(f"Keyboard publisher bound to tcp://{config.host}:{config.port}")
    print("Commands: k=start/stop, i=initial pose, p=pause/resume, [/]=hands")
    print("Prompt change: t <new prompt>")
    print("Quit this publisher with Ctrl+C.")

    try:
        while True:
            text = input("> ").strip()
            if not text:
                continue
            if text.startswith("t "):
                msg = "prompt:" + text[2:].strip()
            else:
                msg = text
            socket.send_string(msg)
            print(f"Sent: {msg}")
    except KeyboardInterrupt:
        print("\nKeyboard publisher stopped.")
    finally:
        socket.close()
        ctx.term()


if __name__ == "__main__":
    main(tyro.cli(InferenceKeyboardConfig))
