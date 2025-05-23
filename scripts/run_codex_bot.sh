#!/bin/bash

# Run the Codex Attribute Bot locally

# Set the repository name
export GITHUB_REPOSITORY="underthemoss/construction-taxonomy"

# Check if OpenAI API key is provided
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable is not set."
    echo "Please set it with: export OPENAI_API_KEY=your_api_key"
    exit 1
fi

# Run the brand-aware Codex attribute bot
python scripts/codex_enhanced_brand_aware.py
