from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, MovieModel
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from schemas.movies import (
    MovieDetailResponseSchema,
    MovieListResponseSchema,
    MovieCreateRequestSchema,
    MovieCreateResponseSchema,
    MovieUpdateRequestSchema,
    CountrySchema,
    NamedEntitySchema,
)

router = APIRouter()


@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movies(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(func.count(MovieModel.id)))
    total_items = count_result.scalar_one()

    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    total_pages = (total_items + per_page - 1) // per_page
    if page > total_pages:
        raise HTTPException(status_code=404, detail="No movies found.")

    offset = (page - 1) * per_page

    result = await db.execute(
        select(MovieModel).order_by(MovieModel.id.desc()).offset(offset).limit(per_page)
    )
    movies = result.scalars().all()
    print(f"{movies=}")

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")
    print(f"{movies=}")

    prev_page = (
        f"/theater/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None
    )
    next_page = (
        f"/theater/movies/?page={page + 1}&per_page={per_page}"
        if page < total_pages
        else None
    )

    return MovieListResponseSchema(
        movies=[MovieDetailResponseSchema.model_validate(movie) for movie in movies],
        prev_page=prev_page,
        next_page=next_page,
        total_pages=total_pages,
        total_items=total_items,
    )


@router.post("/movies/", response_model=MovieCreateResponseSchema, status_code=201)
async def create_movie(
    movie_data: MovieCreateRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    # Проверяем дубликат
    existing = await db.execute(
        select(MovieModel).where(
            MovieModel.name == movie_data.name,
            MovieModel.date == movie_data.date,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=(
                f"A movie with the name '{movie_data.name}' and release date "
                f"'{movie_data.date}' already exists."
            ),
        )

    # Создаём связанные объекты
    country = await get_or_create_country(db, movie_data.country)
    genres = [await get_or_create_genre(db, genre) for genre in movie_data.genres]
    actors = [await get_or_create_actor(db, actor) for actor in movie_data.actors]
    languages = [
        await get_or_create_language(db, language) for language in movie_data.languages
    ]

    # Создаём фильм
    new_movie = MovieModel(
        name=movie_data.name,
        date=movie_data.date,
        score=movie_data.score,
        overview=movie_data.overview,
        status=movie_data.status,
        budget=movie_data.budget,
        revenue=movie_data.revenue,
        country=country,
        genres=genres,
        actors=actors,
        languages=languages,
    )
    db.add(new_movie)
    try:
        await db.commit()
        await db.refresh(new_movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Movie with the same name and date already exists.",  # або інше повідомлення, якщо є специфіка
        )
    await db.commit()

    # Загружаем связанные объекты
    result = await db.execute(
        select(MovieModel)
        .options(
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
            selectinload(MovieModel.country),
        )
        .where(MovieModel.id == new_movie.id)
    )
    movie_with_relations = result.scalar_one()

    return MovieCreateResponseSchema.model_validate(movie_with_relations)


@router.get("/movies/{movie_id}/", response_model=MovieCreateResponseSchema)
async def get_movie_by_id(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MovieModel)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
        .where(MovieModel.id == movie_id)
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found.",
        )

    return MovieCreateResponseSchema.model_validate(movie)


@router.delete("/movies/{movie_id}/", status_code=204)
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )
    await db.delete(movie)
    await db.commit()


@router.patch("/movies/{movie_id}/")
async def update_movie(
    movie_id: int,
    update_data: MovieUpdateRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)

    try:
        await db.commit()
        return {"detail": "Movie updated successfully."}
    except (IntegrityError, SQLAlchemyError):
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


async def get_or_create_country(db, code: str):
    result = await db.execute(select(CountryModel).where(CountryModel.code == code))
    country = result.scalar_one_or_none()
    if country:
        return country

    new_country = CountryModel(code=code, name=None)
    db.add(new_country)
    return new_country


async def get_or_create_genre(db, name: str):
    result = await db.execute(select(GenreModel).where(GenreModel.name == name))
    genre = result.scalar_one_or_none()
    if genre:
        return genre
    new_genre = GenreModel(name=name)
    db.add(new_genre)
    await db.commit()
    await db.refresh(new_genre)
    return new_genre


async def get_or_create_actor(db, name: str):
    result = await db.execute(select(ActorModel).where(ActorModel.name == name))
    actor = result.scalar_one_or_none()
    if actor:
        return actor
    new_actor = ActorModel(name=name)
    db.add(new_actor)
    await db.commit()
    await db.refresh(new_actor)
    return new_actor


async def get_or_create_language(db, name: str):
    result = await db.execute(select(LanguageModel).where(LanguageModel.name == name))
    language = result.scalar_one_or_none()
    if language:
        return language
    new_language = LanguageModel(name=name)
    db.add(new_language)
    await db.commit()
    await db.refresh(new_language)
    return new_language
