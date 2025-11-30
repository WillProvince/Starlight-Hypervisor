#!/bin/bash

# Starlight Startup Script
# Executes startup scripts in /opt/start_scripts/ in numerical order,
# then launches the main Starlight backend.

# Configuration
SCRIPT_DIR=/opt/start_scripts/

mkdir -p $SCRIPT_DIR
chmod 755 $SCRIPT_DIR

echo "--- Starting Starlight Startup Sequence ---"
echo "Executing scripts from: $SCRIPT_DIR"
echo "--------------------------------------------"

# Execute startup scripts in natural sort order
find "$SCRIPT_DIR" -maxdepth 1 -type f -name "*.sh" | sort -V | while read script_file; do
    # Verify script is executable
    if [[ -x "$script_file" ]]; then
        echo "==================================================================="
        echo "== Executing script: $script_file"
        echo "==================================================================="
        
        # Execute the script
        "$script_file"
        
        # Handle script failure
        if [ $? -ne 0 ]; then
            echo ""
            echo "ERROR: $script_file failed with exit code $?"
            echo "Stopping further execution."
            exit 1
        fi
        
        echo "== Finished $script_file successfully."
        echo ""
    else
        echo "Skipping non-executable file: $script_file"
    fi
done

echo "--- Startup sequence complete ---"

# Start the Starlight backend
cd /opt/pyback
exec python3 ./main.py
