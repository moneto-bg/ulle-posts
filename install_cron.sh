#!/bin/bash
# Install the daily ULLE post routine as a macOS launchd job.
# Reads every time from config.json ("schedule.times": ["10:00","19:00"]) and runs
# pipeline.run_daily at each of them, every day (no rest day).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3)"
LABEL="com.ulle.social.daily"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

# Build the <dict> entries for each scheduled time.
INTERVALS="$("$PY" - "$HERE/config.json" <<'PYEOF'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
sched = cfg.get("schedule", {})
times = sched.get("times") or [sched.get("time", "10:00")]
out = []
for t in times:
    h, m = t.split(":")
    out.append(f"    <dict><key>Hour</key><integer>{int(h)}</integer>"
               f"<key>Minute</key><integer>{int(m)}</integer></dict>")
print("\n".join(out))
print("|".join(times), file=sys.stderr)
PYEOF
)"
TIMES="$("$PY" -c "
import json;s=json.load(open('$HERE/config.json'))['schedule']
print(', '.join(s.get('times') or [s.get('time','10:00')]))")"

mkdir -p "$HOME/Library/LaunchAgents" "$HERE/state"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string><string>-m</string><string>pipeline.run_daily</string>
  </array>
  <key>WorkingDirectory</key><string>$HERE</string>
  <key>StartCalendarInterval</key>
  <array>
$INTERVALS
  </array>
  <key>StandardOutPath</key><string>$HERE/state/cron.log</string>
  <key>StandardErrorPath</key><string>$HERE/state/cron.log</string>
  <key>RunAtLoad</key><false/>
</dict></plist>
PLISTEOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✓ Инсталирано: $LABEL"
echo "  Всеки ден в: $TIMES"
echo "  Ръчен тест сега:   cd '$HERE' && $PY -m pipeline.run_daily"
echo "  Чакащи за одобрение: $PY -m pipeline.approve --list"
echo "  Спиране:           launchctl unload '$PLIST'"
echo "  Лог:               $HERE/state/cron.log"
