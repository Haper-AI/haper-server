import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(SCRIPT_DIR, '..', 'model', 'report', 'schema', 'rich_text.json')) as f:
    rich_text_schema = json.dumps(json.load(f))