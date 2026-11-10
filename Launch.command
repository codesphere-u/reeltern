#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -m reeltern.cli gui
else
  exec python3 -m reeltern.cli gui
fi
