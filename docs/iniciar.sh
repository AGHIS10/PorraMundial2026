#!/bin/bash
cd "$(dirname "$0")"
echo "Abriendo Porra Mundial 2026 en http://localhost:8080"
python3 -m http.server 8080
