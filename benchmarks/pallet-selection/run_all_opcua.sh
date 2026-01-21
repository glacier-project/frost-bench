#!/usr/bin/env bash

METRICS=("DistanceMetric" "None")
INSTANCES=("instance_small.json")
OUTPUT_DIR="results/$(uuidgen)/"

FROST_CONFIG="resource/frost_config_opcua.yml"
for METRIC in "${METRICS[@]}"; do
  for INSTANCE in "${INSTANCES[@]}"; do
    echo "Running simulation with FROST_CONFIG=${FROST_CONFIG} METRIC=${METRIC} and INSTANCE=${INSTANCE}"
    INSTANCE_PATH="resource/instance/${INSTANCE}"
    
    FROST_CONFIG="${FROST_CONFIG}" METRIC="${METRIC}" INSTANCE="${INSTANCE_PATH}" OUTPUT_DIR="${OUTPUT_DIR}" ./bin/Conveyor
  done
done