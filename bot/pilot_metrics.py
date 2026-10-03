"""Private operator summary: run with the same database settings as the bot."""
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from bot.pilot_store import pilot_summary

if __name__ == '__main__':
    print(json.dumps(pilot_summary(),ensure_ascii=False,indent=2))
