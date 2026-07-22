#!/bin/bash

# Default number of records to show
N=${1:-3}

# Check if results file exists
if [ ! -f "benchmarks/results.jsonl" ]; then
    echo "Error: benchmarks/results.jsonl file not found!" >&2
    exit 1
fi

# Use python3 to parse JSON lines and format output
python3 -c "
import json
import sys
from datetime import datetime

# Read all lines from the file
with open('benchmarks/results.jsonl', 'r') as f:
    lines = [line.strip() for line in f if line.strip()]

# Get last N lines (or all if less than N)
last_lines = lines[-$N:]

# Print header
print('timestamp           model                     pass_rate tokens_per_sec_gen')
print('------------------- ------------------------- --------- --------------------')

# Process each line
for line in last_lines:
    try:
        data = json.loads(line)
        timestamp = data.get('timestamp', 'N/A')[:19]  # Truncate to date/time only
        model = data.get('model', 'N/A')
        results = data.get('results', {})
        pass_rate = results.get('pass_rate', 0)
        tokens_per_sec_gen = results.get('tokens_per_sec_gen', 0)

        # Format the output line
        print(f'{timestamp:<19} {model:<25} {pass_rate:<9} {tokens_per_sec_gen}')
    except Exception as e:
        print(f'Error parsing line: {e}', file=sys.stderr)
"