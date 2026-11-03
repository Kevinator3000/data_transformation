#!/usr/bin/env bash
# Arbeitet die Queue Einheit für Einheit ab – je Einheit eine frische Claude-Sitzung.
# Aufruf:  ./run_agent.sh            (Standard: höchstens 50 Einheiten)
#          MAX=3 ./run_agent.sh      (zum Ausprobieren)
set -uo pipefail
umask 002
cd "$(dirname "$0")"
mkdir -p logs

MAX=${MAX:-50}
MAX_TURNS=${MAX_TURNS:-100}
PROMPT='Lies AGENTS.md. Führe die Startroutine aus und bearbeite genau EINE Einheit:
die unterbrochene (in_progress) oder sonst die nächste startbare. Schließe sie mit
scripts/queue_cli.py ab (done, submit oder block mit Begründung) und committe.
Führe alle Python-Befehle mit "uv run" aus. Kein git push. Beende dich danach.'

letzte=""
wiederholung=0

for i in $(seq 1 "$MAX"); do
  # erste Einheitszeile in der Statusausgabe = unterbrochene oder nächste startbare
  einheit=$(uv run python scripts/queue_cli.py status | awk '/^P[0-9]-/{print $1; exit}')

  if [[ -z "$einheit" ]]; then
    echo "$(date '+%F %T') Keine startbare Einheit mehr – fertig."
    break
  fi

  if [[ "$einheit" == "$letzte" ]]; then
    wiederholung=$((wiederholung + 1))
    if (( wiederholung >= 2 )); then
      echo "$(date '+%F %T') $einheit kommt nicht voran – Abbruch, bitte Log prüfen."
      break
    fi
  else
    wiederholung=0
  fi
  letzte="$einheit"

  log="logs/$(date +%F_%H%M%S)_${einheit}.log"
  echo "$(date '+%F %T') [$i/$MAX] $einheit → $log"
  claude -p "$PROMPT" --max-turns "$MAX_TURNS" > "$log" 2>&1
  echo "$(date '+%F %T') Exit-Code $? für $einheit"
done

uv run python scripts/queue_cli.py status
