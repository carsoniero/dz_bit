from fastapi import Query
from models.models import Link
from auth.database import get_async_session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
from auth.database import User
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import RedirectResponse
from redis import asyncio as aioredis
from auth.router import router as auth_router
from auth.security import get_current_user_optional, current_active_user



app = FastAPI()

app.include_router(auth_router)





# Модель для создания/обновления ссылки
class LinkRequest(BaseModel):
    original_url: str
    custom_alias: Optional[str] = None


# Модель ответа
class LinkResponse(BaseModel):
    short_code: str
    original_url: str
    owner_id: Optional[int] = None

class ErrorResponse(BaseModel):
    detail: str

# Генерация уникального короткого кода
def generate_short_code():
    return str(uuid.uuid4())[:8]



from sqlalchemy.future import select

current_user = get_current_user_optional

async def get_optional_user(user: Optional[User] = Depends(current_user, use_cache=True)) -> Optional[User]:
    return user

@app.post("/links/shorten", response_model=LinkResponse)
async def shorten_link(
    original_url: str = Query(..., description="Оригинальный URL"),
    custom_alias: Optional[str] = Query(None, description="Пользовательский короткий код"),
    db: AsyncSession = Depends(get_async_session),
    user: Optional[User] = Depends(get_optional_user)
):
    short_code = custom_alias or generate_short_code()

    # Проверяем, существует ли уже этот alias
    result = await db.execute(select(Link).filter_by(short_code=short_code))
    existing_link = result.scalars().first()

    if existing_link:
        raise HTTPException(status_code=400, detail="Alias уже существует")

    owner_id = user.id if user else None
    new_link = Link(short_code=short_code, original_url=original_url, owner_id=owner_id)

    db.add(new_link)
    await db.commit()
    await db.refresh(new_link)

    return {"short_code": short_code, "original_url": original_url, "owner_id": owner_id}



# Создание короткой ссылки с временем жизни
@app.post("/links/shorten/time")
async def shorten_link_with_time(original_url: str, custom_alias: Optional[str] = None, expires_at: Optional[datetime] = None, db: AsyncSession = Depends(get_async_session)):
    short_code = custom_alias or str(uuid.uuid4())[:8]
    existing_link = await db.execute(select(Link).filter_by(short_code = short_code))
    if existing_link:
        raise HTTPException(status_code=400, detail="Short code already exists")
    link = Link(short_code=short_code, original_url=original_url, expires_at=expires_at)
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return {"short_code": short_code, "original_url": original_url, "expires_at": expires_at}

from sqlalchemy.future import select

redis = aioredis.from_url("redis://localhost", encoding="utf8", decode_responses=True)

POPULARITY_THRESHOLD = 3  # Число запросов для кеширования
CACHE_EXPIRE = 60  # Время жизни кеша (сек)

async def get_cached_url(short_code: str):
    return await redis.get(f"short_url:{short_code}")

async def set_cached_url(short_code: str, original_url: str):
    await redis.set(f"short_url:{short_code}", original_url, ex=CACHE_EXPIRE)

async def increase_link_counter(short_code: str):
    return await redis.incr(f"short_url_count:{short_code}")

async def get_link_counter(short_code: str):
    count = await redis.get(f"short_url_count:{short_code}")
    return int(count) if count else 0

@app.get("/links/{short_code}", responses={
    307: {"description": "Успешный ответ"},
    404: {
        "description": "Ссылка не найдена",
        "model": ErrorResponse
    },
})
async def redirect_to_url(short_code: str, db: AsyncSession = Depends(get_async_session)):
    cached_url = await get_cached_url(short_code)
    if cached_url:
        return RedirectResponse(url=cached_url, status_code=307)

    # Увеличиваем счетчик запросов
    count = await increase_link_counter(short_code)

    # Запрос в БД, если ссылки нет в кеше
    result = await db.execute(select(Link).filter_by(short_code=short_code))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    # Если ссылка стала популярной, кешируем ее
    if count >= POPULARITY_THRESHOLD:
        await set_cached_url(short_code, link.original_url)

    return RedirectResponse(url=link.original_url, status_code=307)

# 🗑️ DELETE /links/{short_code} – Удалить короткую ссылку
@app.delete("/links/{short_code}")
async def delete_link(short_code: str, db: AsyncSession = Depends(get_async_session),  user: User = Depends(current_active_user)):
    result = await db.execute(select(Link).filter_by(short_code = short_code))
    link = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Требуется аутентификация")
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

        # Проверяем, принадлежит ли ссылка пользователю
    if link.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Недостаточно прав для удаления")
    await db.delete(link)
    await db.commit()
    return {"message": "Ссылка успешно удалена"}

@app.put("/links/{short_code}/update-url", response_model=LinkResponse)
async def rebind_link(
    short_code: str,
    new_url: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_optional_user)
):
    # Ищем существующую короткую ссылку
    result = await db.execute(select(Link).filter_by(short_code=short_code))
    existing_link = result.scalar_one_or_none()

    if not existing_link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    if existing_link.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    # Обновляем длинную ссылку
    existing_link.original_url = new_url

    await db.commit()
    await db.refresh(existing_link)

    return LinkResponse(
        short_code=existing_link.short_code,
        original_url=existing_link.original_url,
        owner_id=existing_link.owner_id
    )


# Статистика по ссылке
@app.get("/links/{short_code}/stats")
async def get_link_stats(short_code: str, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(Link).filter_by(short_code = short_code))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    return {
        "original_url": link.original_url,
        "created_at": link.created_at,
        "visits": link.visits,
        "last_visited": link.last_visited
    }


# Поиск по оригинальному URL
@app.get("/links/url/search")
async def search_link(original_url: str, db: AsyncSession = Depends(get_async_session)):
    print(original_url)
    result = await db.execute(select(Link).filter_by(original_url=original_url))
    print(f"Поиск ссылки с оригинальным URL: {original_url}")
    link = result.scalars().first()
    if not link:
        print(f"Ссылка не найдена: {original_url}")
        raise HTTPException(status_code=404, detail="Link not found")
    return {"short_code": link.short_code}
