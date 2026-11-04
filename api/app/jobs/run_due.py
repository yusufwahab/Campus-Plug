"""Entry point for the Render cron job: python -m app.jobs.run_due"""

import logging

import app.features.promotions.reviews  # noqa: F401  (registers the did-you-buy prompt)
import app.jobs.handlers  # noqa: F401  (registers handlers)
import app.jobs.orders  # noqa: F401
import app.models  # noqa: F401
import app.notify  # noqa: F401  (registers deliver_notification)
from app.db import SessionLocal
from app.jobs.core import run_due


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        result = run_due(db)
    print(f"jobs finished: {result}")


if __name__ == "__main__":
    main()
