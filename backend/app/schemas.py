from datetime import datetime

from pydantic import BaseModel, Field


class PublicSettings(BaseModel):
    title: str
    subtitle: str
    cols: int
    rows: int
    price_pounds: int
    charity_percent: int
    charity_name: str
    hold_days: int
    image_url: str | None


class SettingsUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    subtitle: str = Field(max_length=300)
    price_pounds: int = Field(ge=1, le=1000)
    charity_percent: int = Field(ge=0, le=100)
    charity_name: str = Field(min_length=1, max_length=120)
    hold_days: int = Field(ge=1, le=60)


class GridUpdate(BaseModel):
    cols: int = Field(ge=1, le=30)
    rows: int = Field(ge=1, le=30)


class PublicEntry(BaseModel):
    id: int
    display_name: str
    status: str
    tiles: list[int]
    expires_at: datetime
    has_voted: bool


class Board(BaseModel):
    settings: PublicSettings
    entries: list[PublicEntry]
    tiles_total: int
    tiles_available: int
    tiles_sold: int


class ConfirmRequest(BaseModel):
    tiles: list[int] = Field(min_length=1, max_length=500)
    name: str = Field(min_length=2, max_length=120)
    employee_number: str = Field(min_length=1, max_length=40)
    email: str | None = Field(default=None, max_length=200)


class ConfirmResponse(BaseModel):
    entry: PublicEntry
    total_pounds: int
    message: str


class LockinRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class PrizeIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class PrizeOut(PrizeIn):
    id: int
    position: int


class CharityIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class CharityOut(CharityIn):
    id: int
    position: int
    votes: int


class VoteRequest(BaseModel):
    entry_id: int
    code: str = Field(min_length=1, max_length=32)
    charity_id: int


class VoteResponse(BaseModel):
    charity_name: str
    message: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminEntry(BaseModel):
    id: int
    name: str
    employee_number: str
    email: str | None
    lockin_code: str
    status: str
    tiles: list[int]
    total_pounds: int
    created_at: datetime
    expires_at: datetime
    locked_at: datetime | None
    failed_attempts: int
    charity_vote: str | None


class DrawRequest(BaseModel):
    pool: str = Field(default="locked")  # "locked" | "all_claimed"
    prize_id: int | None = None
    prize_title: str | None = None
    allow_repeat_person: bool = False



class WinnerOut(BaseModel):
    id: int
    tile_number: int
    entry_id: int
    name: str
    employee_number: str
    email: str | None
    prize_id: int | None
    prize_title: str | None
    drawn_at: datetime


class PublicWinner(BaseModel):
    id: int
    tile_number: int
    display_name: str
    prize_title: str | None
    drawn_at: datetime

