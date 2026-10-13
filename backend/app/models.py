from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Settings(Base):
    """Single-row table (id=1) holding raffle configuration."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    title: Mapped[str] = mapped_column(String(120), default="Christmas Charity Raffle")
    subtitle: Mapped[str] = mapped_column(
        String(300), default="Grab a square, support a great cause, and win festive prizes!"
    )
    cols: Mapped[int] = mapped_column(Integer, default=10)
    rows: Mapped[int] = mapped_column(Integer, default=6)
    price_pounds: Mapped[int] = mapped_column(Integer, default=5)
    charity_percent: Mapped[int] = mapped_column(Integer, default=50)
    charity_name: Mapped[str] = mapped_column(String(120), default="our chosen charity")
    hold_days: Mapped[int] = mapped_column(Integer, default=5)
    image_version: Mapped[int] = mapped_column(Integer, default=0)
    image_file: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Entry(Base):
    """A provisional claim (and later lock-in) of one or more tiles by a person."""

    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    employee_number: Mapped[str] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lockin_code: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default="provisional")  # provisional | locked
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tiles: Mapped[list["Tile"]] = relationship(back_populates="entry", order_by="Tile.number")
    vote: Mapped["CharityVote | None"] = relationship(back_populates="entry", uselist=False)


class Tile(Base):
    __tablename__ = "tiles"

    number: Mapped[int] = mapped_column(primary_key=True)  # 1-based
    entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("entries.id", ondelete="SET NULL"), nullable=True, index=True
    )

    entry: Mapped[Entry | None] = relationship(back_populates="tiles")


class Prize(Base):
    __tablename__ = "prizes"

    id: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")


class Charity(Base):
    __tablename__ = "charities"

    id: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    votes: Mapped[list["CharityVote"]] = relationship(back_populates="charity")


class CharityVote(Base):
    __tablename__ = "charity_votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="RESTRICT"), unique=True)
    charity_id: Mapped[int] = mapped_column(ForeignKey("charities.id", ondelete="RESTRICT"))
    voter_key: Mapped[str] = mapped_column(String(120), unique=True)
    voted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    entry: Mapped[Entry] = relationship(back_populates="vote")
    charity: Mapped[Charity] = relationship(back_populates="votes")


class Winner(Base):
    __tablename__ = "winners"

    id: Mapped[int] = mapped_column(primary_key=True)
    tile_number: Mapped[int] = mapped_column(Integer, unique=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="RESTRICT"))
    prize_id: Mapped[int | None] = mapped_column(ForeignKey("prizes.id", ondelete="SET NULL"), nullable=True)
    prize_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    drawn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    entry: Mapped[Entry] = relationship()
    prize: Mapped[Prize | None] = relationship()

