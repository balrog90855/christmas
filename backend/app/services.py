import secrets
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from .models import Charity, CharityVote, Entry, Prize, Settings, Tile, Winner, utcnow
from .schemas import AdminEntry, PublicEntry, PublicSettings, PublicWinner, WinnerOut

# No 0/O/1/I/L to avoid transcription mistakes
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def normalise_code(code: str) -> str:
    cleaned = "".join(c for c in code.upper() if c.isalnum())
    return f"{cleaned[:4]}-{cleaned[4:]}"


def get_settings(db: Session) -> Settings:
    s = db.get(Settings, 1)
    if s is None:
        s = Settings(id=1)
        db.add(s)
        db.flush()
        sync_tiles(db, s)
        db.commit()
    return s


def sync_tiles(db: Session, s: Settings) -> None:
    total = s.cols * s.rows
    existing = set(db.scalars(select(Tile.number)))
    for n in range(1, total + 1):
        if n not in existing:
            db.add(Tile(number=n))
    db.execute(delete(Tile).where(Tile.number > total))


def release_expired(db: Session) -> int:
    expired = list(
        db.scalars(
            select(Entry.id).where(Entry.status == "provisional", Entry.expires_at < utcnow())
        )
    )
    if not expired:
        return 0
    release_entries(db, expired)
    db.commit()
    return len(expired)


def release_entries(db: Session, entry_ids: list[int]) -> None:
    db.execute(update(Tile).where(Tile.entry_id.in_(entry_ids)).values(entry_id=None))
    db.execute(delete(Entry).where(Entry.id.in_(entry_ids)))


def public_settings(s: Settings) -> PublicSettings:
    return PublicSettings(
        title=s.title,
        subtitle=s.subtitle,
        cols=s.cols,
        rows=s.rows,
        price_pounds=s.price_pounds,
        charity_percent=s.charity_percent,
        charity_name=s.charity_name,
        hold_days=s.hold_days,
        image_url=f"/api/image?v={s.image_version}" if s.image_file else None,
    )


def display_name(name: str) -> str:
    parts = name.split()
    if len(parts) <= 1:
        return name.strip()
    return f"{parts[0]} {parts[-1][0].upper()}."


def entries_with_tiles(db: Session) -> list[Entry]:
    return list(
        db.scalars(
            select(Entry).options(selectinload(Entry.tiles)).order_by(Entry.created_at.desc())
        )
    )


def employee_has_voted(db: Session, employee_number: str) -> bool:
    voter_key = employee_number.strip().casefold()
    return bool(db.scalar(select(CharityVote.id).where(CharityVote.voter_key == voter_key)))


def to_public(e: Entry, has_voted: bool | None = None) -> PublicEntry:
    return PublicEntry(
        id=e.id,
        display_name=display_name(e.name),
        status=e.status,
        tiles=[t.number for t in e.tiles],
        expires_at=e.expires_at,
        has_voted=e.vote is not None if has_voted is None else has_voted,
    )


def to_admin(e: Entry, price: int) -> AdminEntry:
    return AdminEntry(
        id=e.id,
        name=e.name,
        employee_number=e.employee_number,
        email=e.email,
        lockin_code=e.lockin_code,
        status=e.status,
        tiles=[t.number for t in e.tiles],
        total_pounds=len(e.tiles) * price,
        created_at=e.created_at,
        expires_at=e.expires_at,
        locked_at=e.locked_at,
        failed_attempts=e.failed_attempts,
        charity_vote=e.vote.charity.name if e.vote else None,
    )


def to_public_winner(w: Winner) -> PublicWinner:
    return PublicWinner(
        id=w.id,
        tile_number=w.tile_number,
        display_name=display_name(w.entry.name),
        prize_title=w.prize_title or (w.prize.title if w.prize else None),
        drawn_at=w.drawn_at,
    )


def to_admin_winner(w: Winner) -> WinnerOut:
    return WinnerOut(
        id=w.id,
        tile_number=w.tile_number,
        entry_id=w.entry_id,
        name=w.entry.name,
        employee_number=w.entry.employee_number,
        email=w.entry.email,
        prize_id=w.prize_id,
        prize_title=w.prize_title or (w.prize.title if w.prize else None),
        drawn_at=w.drawn_at,
    )



def new_expiry(s: Settings):
    return utcnow() + timedelta(days=s.hold_days)


def count_entries(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Entry)) or 0


def run_migrations() -> None:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config as AlembicConfig

    root = Path(__file__).resolve().parent.parent
    cfg = AlembicConfig(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")


def seed(db: Session) -> None:
    get_settings(db)
    if not db.scalar(select(func.count()).select_from(Prize)):
        db.add_all(
            [
                Prize(position=1, title="1st Prize", description="A festive hamper full of treats"),
                Prize(position=2, title="2nd Prize", description="Luxury chocolate selection"),
                Prize(position=3, title="3rd Prize", description="Bottle of bubbly"),
            ]
        )
        db.commit()
