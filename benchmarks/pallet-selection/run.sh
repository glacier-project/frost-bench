#!/usr/bin/env bash
#
# Unified benchmark runner.
#
#   ./run.sh <benchmark> <mode>
#
#   benchmark : distance | lego | movements | recipes
#   mode      : sim | opcua
#
# Examples:
#   ./run.sh lego opcua
#   ./run.sh distance sim
#   ./run.sh movements opcua
#   ./run.sh recipes sim
#
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./run.sh <benchmark> <mode>

  benchmark : distance | lego | movements | recipes
  mode      : sim | opcua

Examples:
  ./run.sh lego opcua
  ./run.sh distance sim
EOF
    exit 1
}

[[ $# -eq 2 ]] || usage

BENCHMARK="$1"
MODE="$2"

case "$MODE" in
    sim | opcua) ;;
    *) echo "Unknown mode '$MODE' (expected sim|opcua)"; usage ;;
esac

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# Per-benchmark configuration: binary, frost config, metrics, output dir prefix.
case "$BENCHMARK" in
    distance)
        METRICS=("DISTANCE" "RANDOM" "ID")
        OUTPUT_DIR="results/distance/${MODE}-${TIMESTAMP}"
        INSTANCE_PATH="resource/instance/instance_empty.json"
        if [[ "$MODE" == "sim" ]]; then
            BIN="./bin/DistanceSim"; FROST_CONFIG="resource/distance_sim.yml"
        else
            BIN="./bin/DistanceOpcua"; FROST_CONFIG="resource/distance_opcua.yml"
        fi
        ;;
    lego)
        METRICS=("DISTANCE" "ID")
        OUTPUT_DIR="results/lego/lego-${MODE}-${TIMESTAMP}"
        if [[ "$MODE" == "sim" ]]; then
            BIN="./bin/LegoSim"; FROST_CONFIG="resource/lego_sim.yml"
        else
            BIN="./bin/LegoOpcua"; FROST_CONFIG="resource/lego_opcua.yml"
        fi
        ;;
    movements)
        METRICS=("DISTANCE" "ID")
        OUTPUT_DIR="results/lego/movements-${MODE}-${TIMESTAMP}"
        if [[ "$MODE" == "sim" ]]; then
            BIN="./bin/LegoMovementsSim"; FROST_CONFIG="resource/lego_movements_sim.yml"
        else
            BIN="./bin/LegoMovementsOpcua"; FROST_CONFIG="resource/lego_movements_opcua.yml"
        fi
        ;;
    recipes)
        METRICS=("DISTANCE" "ID")
        OUTPUT_DIR="results/lego-3-recipes/lego-${MODE}-${TIMESTAMP}"
        if [[ "$MODE" == "sim" ]]; then
            BIN="./bin/LegoRecipesSim"; FROST_CONFIG="resource/lego_recipes_sim.yml"
        else
            BIN="./bin/LegoRecipesOpcua"; FROST_CONFIG="resource/lego_recipes_opcua.yml"
        fi
        ;;
    *)
        echo "Unknown benchmark '$BENCHMARK'"; usage ;;
esac

for METRIC in "${METRICS[@]}"; do
    echo "Running ${BENCHMARK}/${MODE}: FROST_CONFIG=${FROST_CONFIG} METRIC=${METRIC} OUTPUT_DIR=${OUTPUT_DIR}"

    env_args=(
        FROST_CONFIG="${FROST_CONFIG}"
        METRIC="${METRIC}"
        OUTPUT_DIR="${OUTPUT_DIR}"
        RUN_TYPE="${MODE}"
        MPLBACKEND=agg
    )

    # The distance benchmark consumes a scheduling instance; opcua also persists
    # pallet updates.
    if [[ "$BENCHMARK" == "distance" ]]; then
        env_args+=(INSTANCE="${INSTANCE_PATH}")
        [[ "$MODE" == "opcua" ]] && env_args+=(SAVE_PUPDATES="true")
    fi

    env "${env_args[@]}" "${BIN}"
done
