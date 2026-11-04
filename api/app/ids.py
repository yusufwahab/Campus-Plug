from sqlalchemy.orm import Session

from app.models.system import Counter

# Readable platform IDs: CP-P-48213 (product), CP-S-10762 (service), CP-SL-2045 (seller),
# CP-O-90317 (order), CP-D-1184 (dispute).
_START = {"P": 48000, "S": 10000, "SL": 2000, "O": 90000, "D": 1000}


def next_public_id(db: Session, kind: str) -> str:
    counter = db.get(Counter, kind, with_for_update=True)
    if counter is None:
        counter = Counter(kind=kind, value=_START[kind])
        db.add(counter)
    counter.value += 1
    db.flush()
    return f"CP-{kind}-{counter.value}"
