"""Lightweight Isaac-GR00T PolicyServer client.

The official Isaac-GR00T package provides ``gr00t.policy.server_client``.  For
deployment smoke tests we only need its ZMQ client behavior, so this module keeps
``run_vla_inference.py`` usable even when the full training/server package is not
installed in the local inference environment.
"""

from typing import Any

import msgpack_numpy as mnp
import zmq


class _MsgSerializer:
    @staticmethod
    def to_bytes(data: Any) -> bytes:
        return mnp.packb(data, default=mnp.encode)

    @staticmethod
    def from_bytes(data: bytes) -> Any:
        return mnp.unpackb(data, object_hook=mnp.decode, raw=False)


class PolicyClient:
    """Minimal client for the Isaac-GR00T PolicyServer ZMQ API."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5555,
        timeout_ms: int = 15000,
        api_token: str | None = None,
        strict: bool = False,
    ):
        del strict
        self.context = zmq.Context()
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self.api_token = api_token
        self._init_socket()

    def _init_socket(self):
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.socket.connect(f"tcp://{self.host}:{self.port}")

    def ping(self) -> bool:
        try:
            self.call_endpoint("ping", requires_input=False)
            return True
        except zmq.error.ZMQError:
            self._init_socket()
            return False

    def call_endpoint(
        self,
        endpoint: str,
        data: dict | None = None,
        requires_input: bool = True,
    ) -> Any:
        request: dict[str, Any] = {"endpoint": endpoint}
        if requires_input:
            request["data"] = data
        if self.api_token:
            request["api_token"] = self.api_token

        try:
            self.socket.send(_MsgSerializer.to_bytes(request))
            message = self.socket.recv()
        except zmq.error.Again:
            self._init_socket()
            raise

        if message == b"ERROR":
            raise RuntimeError("Server error. Check that the PolicyServer is running.")

        response = _MsgSerializer.from_bytes(message)
        if isinstance(response, dict) and "error" in response:
            raise RuntimeError(f"Server error: {response['error']}")
        return response

    def get_action(
        self,
        observation: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        response = self.call_endpoint(
            "get_action",
            {"observation": observation, "options": options},
        )
        return tuple(response)

    def reset(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.call_endpoint("reset", {"options": options})

    def close(self):
        self.socket.close()
        self.context.term()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
