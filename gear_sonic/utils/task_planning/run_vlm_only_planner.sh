#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_INPUT="/home/autobrik/NONHUMAN/wbcd-icra-2026-deployment/media/wbcd_competition/shelf"
DEFAULT_MODELS_CSV="qwen/qwen3-vl-8b-instruct,google/gemini-2.5-flash,openai/gpt-4.1-mini"
OUTPUT_ROOT="$SCRIPT_DIR/outputs_test"
INPUT_PATH="$DEFAULT_INPUT"
MODEL1="${OPENROUTER_MODEL1:-}"
MODEL2="${OPENROUTER_MODEL2:-}"
MODEL3="${OPENROUTER_MODEL3:-}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$SCRIPT_DIR/.uv-cache}"

if [[ -f "$SCRIPT_DIR/.env" ]]; then
  while IFS='=' read -r key value; do
    case "$key" in
      OPENROUTER_MODEL1)
        MODEL1="${MODEL1:-$value}"
        ;;
      OPENROUTER_MODEL2)
        MODEL2="${MODEL2:-$value}"
        ;;
      OPENROUTER_MODEL3)
        MODEL3="${MODEL3:-$value}"
        ;;
    esac
  done < "$SCRIPT_DIR/.env"
fi

ENV_MODELS_CSV=""
for model in "$MODEL1" "$MODEL2" "$MODEL3"; do
  if [[ -n "$model" ]]; then
    if [[ -n "$ENV_MODELS_CSV" ]]; then
      ENV_MODELS_CSV+=","
    fi
    ENV_MODELS_CSV+="$model"
  fi
done

ENV_MODELS_CSV="${ENV_MODELS_CSV:-$DEFAULT_MODELS_CSV}"
MODELS_CSV="$ENV_MODELS_CSV"

usage() {
  cat <<EOF
Usage:
  ./run_vlm_only_planner.sh [--input PATH] [--output-root DIR] [--all] [--models MODEL1,MODEL2,...]

Examples:
  ./run_vlm_only_planner.sh
  ./run_vlm_only_planner.sh --input /path/to/image_or_folder
  ./run_vlm_only_planner.sh --input /path/to/image.png --all
  ./run_vlm_only_planner.sh --input /path/to/image.png --models qwen/qwen3-vl-8b-instruct,google/gemini-2.5-flash,openai/gpt-4.1-mini

Notes:
  --all uses only OPENROUTER_MODEL1, OPENROUTER_MODEL2, and OPENROUTER_MODEL3 from .env.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --input)
      INPUT_PATH="${2:?Missing value for --input}"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="${2:?Missing value for --output-root}"
      shift 2
      ;;
    --models)
      MODELS_CSV="${2:?Missing value for --models}"
      shift 2
      ;;
    --all)
      MODELS_CSV="all"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

RUN_NAME="vlm_only-$(date +%Y-%m-%d_%H-%M-%S)"
OUTPUT_DIR="$OUTPUT_ROOT/$RUN_NAME"
PLANNER="$SCRIPT_DIR/vlm_only_planner.py"

if [[ "$MODELS_CSV" == "all" ]]; then
  if [[ "$ENV_MODELS_CSV" == "all" || -z "$ENV_MODELS_CSV" ]]; then
    MODELS_CSV="$DEFAULT_MODELS_CSV"
  else
    MODELS_CSV="$ENV_MODELS_CSV"
  fi
fi

IFS=',' read -r -a MODELS <<< "$MODELS_CSV"

mkdir -p "$OUTPUT_DIR"

safe_model_name() {
  local model="$1"
  model="${model//\//__}"
  model="${model//:/__}"
  echo "$model"
}

run_one() {
  local image_path="$1"
  local model="$2"
  local stem
  local safe_model
  stem="$(basename "$image_path")"
  stem="${stem%.*}"
  safe_model="$(safe_model_name "$model")"

  mkdir -p "$OUTPUT_DIR/$safe_model"

  echo "Processing [$model]: $image_path"
  uv run python "$PLANNER" \
    --image "$image_path" \
    --model "$model" \
    --output "$OUTPUT_DIR/$safe_model/${stem}_result.json"
}

cd "$SCRIPT_DIR"
echo "Run output directory: $OUTPUT_DIR"
echo "Models: ${MODELS[*]}"

if [[ -d "$INPUT_PATH" ]]; then
  shopt -s nullglob nocaseglob
  images=("$INPUT_PATH"/*.png "$INPUT_PATH"/*.jpg "$INPUT_PATH"/*.jpeg)
  shopt -u nocaseglob

  if [[ "${#images[@]}" -eq 0 ]]; then
    echo "No .png/.jpg/.jpeg images found in: $INPUT_PATH" >&2
    exit 1
  fi

  for image_path in "${images[@]}"; do
    for model in "${MODELS[@]}"; do
      run_one "$image_path" "$model"
    done
  done
elif [[ -f "$INPUT_PATH" ]]; then
  for model in "${MODELS[@]}"; do
    run_one "$INPUT_PATH" "$model"
  done
else
  echo "Input path does not exist: $INPUT_PATH" >&2
  exit 1
fi

echo "Done: $OUTPUT_DIR"
