"""Interactive account setup and password rotation. No password is stored in source or logs."""
import argparse
import getpass
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import security
from app.models import User


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "change"))
    parser.add_argument("username", nargs="?", choices=("admin", "virtual"))
    args = parser.parse_args()
    targets = (args.username,) if args.username else ("admin", "virtual")
    for username in targets:
        role = "ADMIN" if username == "admin" else "VIRTUAL"
        with Session(security.engine) as db:
            existing = db.scalar(select(User.id).where(User.username == username)) is not None
        if args.action == "init" and existing:
            print(f"{username}: account already exists; password unchanged")
            continue
        if args.action == "change" and not existing:
            raise SystemExit(f"{username}: account does not exist; run init first")
        password = getpass.getpass(f"{username} yeni şifrə: ")
        confirmation = getpass.getpass("Şifrəni təkrar daxil edin: ")
        if password != confirmation or not password:
            raise SystemExit("Şifrələr uyğun gəlmir və ya boşdur.")
        if args.action == "change":
            if len(password) < 12:
                raise SystemExit("Yeni ictimai domen şifrəsi ən azı 12 simvol olmalıdır.")
            security.upsert_demo_user(username, password, role)
        else:
            security.create_if_missing(username, password, role)
        print(f"{username}: hesab hazırdır; şifrə bazada hash kimi saxlandı")


if __name__ == "__main__":
    main()
