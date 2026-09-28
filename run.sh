#!/usr/bin/env bash
# Launch the investigator dashboard on Linux.
#   ./run.sh            -> start Streamlit
#   ./run.sh test       -> headless acceptance test (no Streamlit needed)
#   ./run.sh setup      -> create .venv and install dependencies
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ] || [ "${1:-}" = "setup" ]; then
  echo "[*] Creating virtual environment in .venv"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip -q
  pip install -r requirements.txt
  [ "${1:-}" = "setup" ] && { echo "[*] Setup complete. Run ./run.sh to start."; exit 0; }
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [ ! -f data/cases.json ]; then
  echo "[*] Generating synthetic dataset"
  python3 tools/generate_data.py
fi

case "${1:-run}" in
  test)   python3 tests/run_cases.py ;;
  smoke)  python3 tests/smoke_app.py ;;
  data)   python3 tools/generate_data.py ;;
  *)      echo "[*] Starting dashboard on http://localhost:8501"
          streamlit run app.py ;;
esac
