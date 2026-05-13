#!/usr/bin/env python3
"""Minimal VLM caller for shelf picking."""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


DEFAULT_VLM_MODEL = "qwen/qwen3-vl-8b-instruct"
DEFAULT_MAX_TOKENS = 256
DEFAULT_REASONING_EFFORT = "none"
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
SCRIPT_DIR = Path(__file__).resolve().parent
PROMPT_PATH = SCRIPT_DIR / "vlm_only_prompt.txt"


def encode_image_base64(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def get_model(cli_model: str | None) -> str:
    return cli_model or os.getenv("OPENROUTER_MODEL1", DEFAULT_VLM_MODEL)


def get_max_tokens() -> int:
    return int(os.getenv("OPENROUTER_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))


def get_reasoning_effort() -> str:
    return os.getenv("OPENROUTER_REASONING_EFFORT", DEFAULT_REASONING_EFFORT)


def call_openrouter(image_path: Path, model: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{encode_image_base64(image_path)}",
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": get_max_tokens(),
        "reasoning": {
            "effort": get_reasoning_effort(),
            "exclude": True,
        },
        "include_reasoning": False,
    }

    response = requests.post(
        OPENROUTER_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/",
            "X-Title": "vlm-only-shelf-planner",
        },
        json=payload,
        timeout=90,
    )
    response.raise_for_status()

    response_data = response.json()
    content = response_data["choices"][0]["message"].get("content")
    if isinstance(content, str):
        return content
    return json.dumps(response_data, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal VLM-only shelf planner.")
    parser.add_argument("--image", required=True, help="Path to the input image.")
    parser.add_argument("--model", help="OpenRouter model override.")
    parser.add_argument("--output", help="Path to write result JSON.")
    args = parser.parse_args()

    load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

    image_path = Path(args.image)
    if not image_path.is_file():
        raise FileNotFoundError(f"Image does not exist: {image_path}")

    model = get_model(args.model)
    started_at = time.perf_counter()
    try:
        vlm_output = call_openrouter(image_path, model)
        result: dict[str, Any] = {
            "image": str(image_path),
            "model": model,
            "inference_time_seconds": round(time.perf_counter() - started_at, 3),
            "vlm_output": vlm_output,
        }
    except Exception as exc:
        result = {
            "image": str(image_path),
            "model": model,
            "inference_time_seconds": round(time.perf_counter() - started_at, 3),
            "error": str(exc),
            "vlm_output": None,
        }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
