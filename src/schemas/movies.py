from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from datetime import date
from database import get_db, MovieModel
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from pydantic import BaseModel, ConfigDict, conint, constr, Field
from typing import List
from typing import Optional
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, constr, validator
from datetime import date, timedelta


router = APIRouter()


class MovieStatus(str, Enum):
    released = "Released"
    post_production = "Post Production"
    in_production = "In Production"


class MovieDetailResponseSchema(BaseModel):
    id: int
    name: str
    date: date
    score: float = Field(..., ge=0, le=10)
    overview: str

    model_config = ConfigDict(from_attributes=True)


class MovieListResponseSchema(BaseModel):
    movies: List[MovieDetailResponseSchema]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int
    model_config = ConfigDict(from_attributes=True)


class CountrySchema(BaseModel):
    id: int
    code: str
    name: str | None
    model_config = ConfigDict(from_attributes=True)


class NamedEntitySchema(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class MovieCreateResponseSchema(BaseModel):
    id: int
    name: str
    date: date
    score: float
    overview: str
    status: str
    budget: float
    revenue: float
    country: CountrySchema
    genres: List[NamedEntitySchema]
    actors: List[NamedEntitySchema]
    languages: List[NamedEntitySchema]

    model_config = ConfigDict(from_attributes=True)


class MovieUpdateRequestSchema(BaseModel):
    name: Optional[constr(max_length=255)] = None
    date: Optional[date] = None
    score: Optional[float] = Field(None, ge=0, le=100)
    overview: Optional[str] = None
    status: Optional[MovieStatus] = None
    budget: Optional[float] = Field(None, ge=0)
    revenue: Optional[float] = Field(None, ge=0)

    @validator("date")
    def validate_date(cls, value):
        if value and value > date.today() + timedelta(days=365):
            raise ValueError("Date cannot be more than 1 year in the future.")
        return value


class MovieCreateRequestSchema(BaseModel):
    name: constr(max_length=255)
    date: date
    score: float = Field(..., ge=0, le=100)
    overview: str
    status: MovieStatus
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)
    country: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    genres: List[str]
    actors: List[str]
    languages: List[str]

    @validator("date")
    def validate_date(cls, value):
        if value > date.today() + timedelta(days=365):
            raise ValueError("Date cannot be more than 1 year in the future.")
        return value
