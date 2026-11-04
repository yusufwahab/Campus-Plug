"""Operator commands: python -m app.cli <command>."""

import argparse
import getpass

from sqlalchemy import select

from app.db import SessionLocal
from app.features.catalogue.reference import seed_reference
from app.models.identity import User
from app.security import hash_password


def create_admin(email: str, name: str) -> None:
    password = getpass.getpass("Password (min 12 chars): ")
    if len(password) < 12:
        raise SystemExit("Password too short")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email.lower())):
            raise SystemExit("User already exists")
        db.add(
            User(
                email=email.lower(),
                full_name=name,
                role="admin",
                password_hash=hash_password(password),
                email_verified=True,
                onboarded=True,
            )
        )
        db.commit()
    print("Admin created. Sign in and enrol two-step sign-in (TOTP) on first login.")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    admin = sub.add_parser("create-admin")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    sub.add_parser("seed-reference")
    pre = sub.add_parser("preflight", help="Check the configuration without printing any secret")
    pre.add_argument("--online", action="store_true", help="Also make one harmless read-only call to each service")
    args = parser.parse_args()
    if args.cmd == "preflight":
        from app.preflight import run

        raise SystemExit(run(args.online))
    if args.cmd == "create-admin":
        create_admin(args.email, args.name)
    elif args.cmd == "seed-reference":
        with SessionLocal() as db:
            seed_reference(db)
        print("Reference data ready.")


if __name__ == "__main__":
    main()
