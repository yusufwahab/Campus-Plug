"""Write the OpenAPI schema used to generate the typed web client: python scripts/export_openapi.py"""

import json
from pathlib import Path

from app.main import app

Path(__file__).resolve().parent.parent.joinpath("openapi.json").write_text(json.dumps(app.openapi(), indent=2))
