#!/bin/bash
# start_mlx.sh
# Script to start the local MLX endpoint pointing to LFM-24B-4bit on Canmore
# Runs on Port 8090, which is exported directly via Tailscale

echo "Starting MLX-LM Server..."
# Activate the virtual environment observed on Canmore
source ~/venv-lfm2/bin/activate

# Execute the local LLM server
# Uses the LiquidAI LFM2 24B 4-bit model
mlx_lm.server --model mlx-community/Liquid-LFM-24B-4Bit --port 8090 --host 127.0.0.1
