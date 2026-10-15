import asyncio
import io
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from . import services
from .auth import authenticate, create_token, require_admin
from .config import config
from .db import Base, SessionLocal, engine, get_db
from .models import Charity, CharityVote, Entry, Prize, Tile, Winner
from .schemas import (
    AdminEntry,
    Board,
    CharityIn,
    CharityOut,
    ConfirmRequest,
    ConfirmResponse,
    DrawRequest,
    GridUpdate,
    LockinRequest,
    LoginRequest,
    PrizeIn,
    PrizeOut,
    PublicEntry,
    PublicSettings,
    PublicWinner,
    SettingsUpdate,
    TokenResponse,
    VoteRequest,
    VoteResponse,
    WinnerOut,
)


async def _expiry_loop():
    while True:
        try:
            with SessionLocal() as db:
                services.release_expired(db)
        except Exception as exc:  # keep the loop alive
            print("expiry sweep failed:", exc)
        await asyncio.sleep(600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    services.run_migrations()
    config.upload_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        services.seed(db)
    task = asyncio.create_task(_expiry_loop())
    yield
    task.cancel()


app = FastAPI(title="Christmas Raffle API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in config.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- public

@app.get("/api/board", response_model=Board)
def board(db: Session = Depends(get_db)):
    services.release_expired(db)
    s = services.get_settings(db)
    entries = services.entries_with_tiles(db)
    total = s.cols * s.rows
    taken = sum(len(e.tiles) for e in entries)
    sold = sum(len(e.tiles) for e in entries if e.status == "locked")
    voted_keys = set(db.scalars(select(CharityVote.voter_key)))
    return Board(
        settings=services.public_settings(s),
        entries=[
            services.to_public(e, e.employee_number.strip().casefold() in voted_keys)
            for e in entries
        ],
        tiles_total=total,
        tiles_available=total - taken,
        tiles_sold=sold,
    )


@app.get("/api/prizes", response_model=list[PrizeOut])
def list_prizes(db: Session = Depends(get_db)):
    return db.scalars(select(Prize).order_by(Prize.position, Prize.id)).all()


@app.get("/api/charities", response_model=list[CharityOut])
def list_charities(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Charity, func.count(CharityVote.id))
        .outerjoin(CharityVote, CharityVote.charity_id == Charity.id)
        .group_by(Charity.id)
        .order_by(Charity.position, Charity.id)
    ).all()
    return [
        CharityOut(
            id=charity.id,
            position=charity.position,
            name=charity.name,
            description=charity.description,
            votes=count,
        )
        for charity, count in rows
    ]


@app.get("/api/winners", response_model=list[PublicWinner])
def list_public_winners(db: Session = Depends(get_db)):
    winners = db.scalars(
        select(Winner)
        .options(selectinload(Winner.entry), selectinload(Winner.prize))
        .order_by(Winner.drawn_at.asc())
    ).all()
    return [services.to_public_winner(w) for w in winners]



@app.get("/api/image")
def get_image(db: Session = Depends(get_db)):
    s = services.get_settings(db)
    if not s.image_file:
        raise HTTPException(404, "No image uploaded")
    path = config.upload_dir / s.image_file
    if not path.is_file():
        raise HTTPException(404, "No image uploaded")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000"})


@app.post("/api/entries", response_model=ConfirmResponse, status_code=201)
def confirm_selection(body: ConfirmRequest, db: Session = Depends(get_db)):
    services.release_expired(db)
    s = services.get_settings(db)
    tiles = sorted(set(body.tiles))
    if tiles[0] < 1 or tiles[-1] > s.cols * s.rows:
        raise HTTPException(400, "Invalid tile selection")

    entry = Entry(
        name=body.name.strip(),
        employee_number=body.employee_number.strip(),
        email=(body.email or "").strip() or None,
        lockin_code=services.generate_code(),
        expires_at=services.new_expiry(s),
    )
    db.add(entry)
    db.flush()
    # Atomic claim: only tiles that are still free are updated
    result = db.execute(
        update(Tile).where(Tile.number.in_(tiles), Tile.entry_id.is_(None)).values(entry_id=entry.id)
    )
    if result.rowcount != len(tiles):
        db.rollback()
        raise HTTPException(409, "Some of those squares were just taken. Please pick again.")
    db.commit()
    entry = db.scalar(
        select(Entry).options(selectinload(Entry.tiles)).where(Entry.id == entry.id)
    )
    return ConfirmResponse(
        entry=services.to_public(entry),
        total_pounds=len(tiles) * s.price_pounds,
        message=(
            f"Squares held for {s.hold_days} days. Pay £{len(tiles) * s.price_pounds} to the "
            "organiser to receive your lock-in code, then enter it from the sidebar."
        ),
    )


@app.post("/api/entries/{entry_id}/lockin", response_model=PublicEntry)
def lock_in(entry_id: int, body: LockinRequest, db: Session = Depends(get_db)):
    services.release_expired(db)
    entry = db.scalar(
        select(Entry).options(selectinload(Entry.tiles)).where(Entry.id == entry_id)
    )
    if entry is None:
        raise HTTPException(404, "This selection no longer exists (it may have expired).")
    if entry.status == "locked":
        return services.to_public(entry, services.employee_has_voted(db, entry.employee_number))
    if entry.failed_attempts >= config.max_lockin_attempts:
        raise HTTPException(429, "Too many wrong codes. Please contact the organiser.")
    if not secrets.compare_digest(
        services.normalise_code(body.code).encode(), entry.lockin_code.encode()
    ):
        entry.failed_attempts += 1
        db.commit()
        raise HTTPException(400, "That lock-in code is not correct.")
    entry.status = "locked"
    entry.locked_at = services.utcnow()
    entry.failed_attempts = 0
    db.commit()
    return services.to_public(entry, services.employee_has_voted(db, entry.employee_number))


@app.post("/api/votes", response_model=VoteResponse, status_code=201)
def cast_vote(body: VoteRequest, db: Session = Depends(get_db)):
    services.release_expired(db)
    entry = db.scalar(select(Entry).where(Entry.id == body.entry_id))
    if entry is None:
        raise HTTPException(404, "This selection no longer exists.")
    if entry.status != "locked":
        raise HTTPException(403, "Lock in your squares before voting.")
    if entry.failed_attempts >= config.max_lockin_attempts:
        raise HTTPException(429, "Too many wrong codes. Please contact the organiser.")
    if not secrets.compare_digest(
        services.normalise_code(body.code).encode(), entry.lockin_code.encode()
    ):
        entry.failed_attempts += 1
        db.commit()
        raise HTTPException(400, "That lock-in code is not correct.")
    voter_key = entry.employee_number.strip().casefold()
    if db.scalar(select(CharityVote.id).where(CharityVote.voter_key == voter_key)):
        raise HTTPException(409, "This employee number has already voted.")
    charity = db.get(Charity, body.charity_id)
    if charity is None:
        raise HTTPException(404, "That charity option is no longer available.")
    db.add(CharityVote(entry_id=entry.id, charity_id=charity.id, voter_key=voter_key))
    entry.failed_attempts = 0
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This employee number has already voted.")
    return VoteResponse(charity_name=charity.name, message="Your vote has been recorded.")


# ----------------------------------------------------------------- admin

@app.post("/api/admin/login", response_model=TokenResponse)
def login(body: LoginRequest):
    if not authenticate(body.username, body.password):
        raise HTTPException(401, "Incorrect username or password")
    return TokenResponse(access_token=create_token())


admin_deps = [Depends(require_admin)]


@app.get("/api/admin/entries", response_model=list[AdminEntry], dependencies=admin_deps)
def admin_entries(db: Session = Depends(get_db)):
    services.release_expired(db)
    s = services.get_settings(db)
    return [services.to_admin(e, s.price_pounds) for e in services.entries_with_tiles(db)]


def _get_entry(db: Session, entry_id: int) -> Entry:
    entry = db.scalar(
        select(Entry).options(selectinload(Entry.tiles)).where(Entry.id == entry_id)
    )
    if entry is None:
        raise HTTPException(404, "Entry not found")
    return entry


@app.post(
    "/api/admin/entries/{entry_id}/regenerate", response_model=AdminEntry, dependencies=admin_deps
)
def regenerate(entry_id: int, db: Session = Depends(get_db)):
    s = services.get_settings(db)
    entry = _get_entry(db, entry_id)
    entry.lockin_code = services.generate_code()
    entry.failed_attempts = 0
    if entry.status == "provisional":
        entry.expires_at = services.new_expiry(s)
    db.commit()
    return services.to_admin(entry, s.price_pounds)


@app.post(
    "/api/admin/entries/{entry_id}/lock", response_model=AdminEntry, dependencies=admin_deps
)
def admin_lock(entry_id: int, db: Session = Depends(get_db)):
    s = services.get_settings(db)
    entry = _get_entry(db, entry_id)
    entry.status = "locked"
    entry.locked_at = entry.locked_at or services.utcnow()
    db.commit()
    return services.to_admin(entry, s.price_pounds)


@app.delete("/api/admin/entries", status_code=204, dependencies=admin_deps)
def admin_reset_all(db: Session = Depends(get_db)):
    """Wipe every entry, vote and draw result; all squares become available again."""
    db.execute(delete(Winner))
    db.execute(delete(CharityVote))
    db.execute(update(Tile).values(entry_id=None))
    db.execute(delete(Entry))
    db.commit()


@app.delete("/api/admin/entries/{entry_id}", status_code=204, dependencies=admin_deps)
def admin_release(entry_id: int, db: Session = Depends(get_db)):
    _get_entry(db, entry_id)
    if db.scalar(select(Winner.id).where(Winner.entry_id == entry_id)):
        raise HTTPException(409, "This entry holds a winning raffle tile. Remove the winner draw first.")
    if db.scalar(select(CharityVote.id).where(CharityVote.entry_id == entry_id)):
        raise HTTPException(409, "This entry has voted and cannot be released.")
    services.release_entries(db, [entry_id])
    db.commit()


@app.get("/api/admin/settings", response_model=PublicSettings, dependencies=admin_deps)
def admin_get_settings(db: Session = Depends(get_db)):
    return services.public_settings(services.get_settings(db))


@app.put("/api/admin/settings", response_model=PublicSettings, dependencies=admin_deps)
def admin_update_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    s = services.get_settings(db)
    for key, value in body.model_dump().items():
        setattr(s, key, value)
    db.commit()
    return services.public_settings(s)


@app.put("/api/admin/grid", response_model=PublicSettings, dependencies=admin_deps)
def admin_update_grid(body: GridUpdate, db: Session = Depends(get_db)):
    if services.count_entries(db):
        raise HTTPException(
            409, "Release all entries before changing the grid size (it would affect claimed squares)."
        )
    s = services.get_settings(db)
    s.cols, s.rows = body.cols, body.rows
    services.sync_tiles(db, s)
    db.commit()
    return services.public_settings(s)


@app.post("/api/admin/image", response_model=PublicSettings, dependencies=admin_deps)
async def admin_upload_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read(config.max_upload_bytes + 1)
    if len(data) > config.max_upload_bytes:
        raise HTTPException(413, "Image is too large (max 8MB)")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "That file is not a valid image")
    img = img.convert("RGB")
    img.thumbnail((2400, 2400))
    s = services.get_settings(db)
    old = s.image_file
    s.image_version += 1
    s.image_file = f"raffle_{s.image_version}.jpg"
    img.save(config.upload_dir / s.image_file, "JPEG", quality=88)
    db.commit()
    if old:
        (config.upload_dir / old).unlink(missing_ok=True)
    return services.public_settings(s)


@app.delete("/api/admin/image", response_model=PublicSettings, dependencies=admin_deps)
def admin_delete_image(db: Session = Depends(get_db)):
    s = services.get_settings(db)
    if s.image_file:
        (config.upload_dir / s.image_file).unlink(missing_ok=True)
    s.image_file = None
    s.image_version += 1
    db.commit()
    return services.public_settings(s)


@app.post("/api/admin/prizes", response_model=PrizeOut, status_code=201, dependencies=admin_deps)
def create_prize(body: PrizeIn, db: Session = Depends(get_db)):
    nxt = (db.scalar(select(func.max(Prize.position))) or 0) + 1
    prize = Prize(position=nxt, **body.model_dump())
    db.add(prize)
    db.commit()
    return prize


@app.put("/api/admin/prizes/{prize_id}", response_model=PrizeOut, dependencies=admin_deps)
def update_prize(prize_id: int, body: PrizeIn, db: Session = Depends(get_db)):
    prize = db.get(Prize, prize_id)
    if prize is None:
        raise HTTPException(404, "Prize not found")
    prize.title, prize.description = body.title, body.description
    db.commit()
    return prize


@app.delete("/api/admin/prizes/{prize_id}", status_code=204, dependencies=admin_deps)
def delete_prize(prize_id: int, db: Session = Depends(get_db)):
    prize = db.get(Prize, prize_id)
    if prize is None:
        raise HTTPException(404, "Prize not found")
    db.delete(prize)
    db.commit()


@app.get(
    "/api/admin/charities", response_model=list[CharityOut], dependencies=admin_deps
)
def admin_charities(db: Session = Depends(get_db)):
    return list_charities(db)


@app.post(
    "/api/admin/charities",
    response_model=CharityOut,
    status_code=201,
    dependencies=admin_deps,
)
def create_charity(body: CharityIn, db: Session = Depends(get_db)):
    position = (db.scalar(select(func.max(Charity.position))) or 0) + 1
    charity = Charity(position=position, **body.model_dump())
    db.add(charity)
    db.commit()
    return CharityOut(
        id=charity.id,
        position=charity.position,
        name=charity.name,
        description=charity.description,
        votes=0,
    )


@app.put(
    "/api/admin/charities/{charity_id}",
    response_model=CharityOut,
    dependencies=admin_deps,
)
def update_charity(charity_id: int, body: CharityIn, db: Session = Depends(get_db)):
    charity = db.get(Charity, charity_id)
    if charity is None:
        raise HTTPException(404, "Charity not found")
    charity.name, charity.description = body.name, body.description
    db.commit()
    return CharityOut(
        id=charity.id,
        position=charity.position,
        name=charity.name,
        description=charity.description,
        votes=db.scalar(
            select(func.count(CharityVote.id)).where(CharityVote.charity_id == charity.id)
        )
        or 0,
    )


@app.delete(
    "/api/admin/charities/{charity_id}",
    status_code=204,
    dependencies=admin_deps,
)
def delete_charity(charity_id: int, db: Session = Depends(get_db)):
    charity = db.get(Charity, charity_id)
    if charity is None:
        raise HTTPException(404, "Charity not found")
    if db.scalar(
        select(func.count(CharityVote.id)).where(CharityVote.charity_id == charity.id)
    ):
        raise HTTPException(409, "A charity with votes cannot be deleted.")
    db.delete(charity)
    db.commit()


@app.get("/api/admin/winners", response_model=list[WinnerOut], dependencies=admin_deps)
def admin_list_winners(db: Session = Depends(get_db)):
    winners = db.scalars(
        select(Winner)
        .options(selectinload(Winner.entry), selectinload(Winner.prize))
        .order_by(Winner.drawn_at.asc())
    ).all()
    return [services.to_admin_winner(w) for w in winners]


@app.post("/api/admin/draw", response_model=WinnerOut, dependencies=admin_deps)
def admin_draw_winner(body: DrawRequest, db: Session = Depends(get_db)):
    existing_winners = db.scalars(
        select(Winner).options(selectinload(Winner.entry))
    ).all()
    won_tiles = {w.tile_number for w in existing_winners}
    won_employees = {
        w.entry.employee_number.strip().lower()
        for w in existing_winners
        if w.entry and w.entry.employee_number
    }

    prize = None
    prize_title = body.prize_title
    if body.prize_id is not None:
        prize = db.get(Prize, body.prize_id)
        if prize is None:
            raise HTTPException(404, "Prize not found")
        if not prize_title:
            prize_title = prize.title

    stmt = (
        select(Tile)
        .join(Tile.entry)
        .options(selectinload(Tile.entry))
        .where(Tile.entry_id.is_not(None))
    )
    if body.pool == "locked":
        stmt = stmt.where(Entry.status == "locked")
    else:
        stmt = stmt.where(Entry.status.in_(["locked", "provisional"]))

    candidates = db.scalars(stmt).all()

    eligible = [t for t in candidates if t.number not in won_tiles]

    if not body.allow_repeat_person:
        eligible = [
            t
            for t in eligible
            if t.entry and t.entry.employee_number.strip().lower() not in won_employees
        ]

    if not eligible:
        raise HTTPException(
            400,
            "No eligible squares remain in the selected pool to draw from.",
        )

    winning_tile = secrets.choice(eligible)

    winner = Winner(
        tile_number=winning_tile.number,
        entry_id=winning_tile.entry_id,
        prize_id=body.prize_id,
        prize_title=prize_title,
        drawn_at=services.utcnow(),
    )
    db.add(winner)
    db.commit()
    db.refresh(winner)
    db.refresh(winner, ["entry", "prize"])
    return services.to_admin_winner(winner)


@app.delete("/api/admin/winners/{winner_id}", status_code=204, dependencies=admin_deps)
def admin_delete_winner(winner_id: int, db: Session = Depends(get_db)):
    winner = db.get(Winner, winner_id)
    if winner is None:
        raise HTTPException(404, "Winner record not found")
    db.delete(winner)
    db.commit()


@app.delete("/api/admin/winners", status_code=204, dependencies=admin_deps)
def admin_reset_winners(db: Session = Depends(get_db)):
    db.execute(delete(Winner))
    db.commit()
