import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app import app, get_async_session, redis
from models.models import Base, Link, User
from auth.security import create_access_token
from auth.database import DATABASE_URL
pytestmark = pytest.mark.asyncio

engine = create_async_engine(DATABASE_URL, echo=True)
TestingSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession
)


# Фикстура для переопределения зависимостей
@pytest.fixture(scope="function")
async def test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="module")
def test_client():
    app.dependency_overrides[get_async_session] = lambda: TestingSessionLocal()
    with TestClient(app) as client:
        yield client


# Фикстура для тестового пользователя
@pytest.fixture(scope="module")
def test_user():
    return User(
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="fakehashedsecret",
        is_active=True
    )


# Фикстура для тестового токена
@pytest.fixture(scope="module")
def test_token(test_user):
    return create_access_token(data={"sub": test_user.username})


# Тесты для эндпоинтов
class TestShortenLink:
    async def test_create_short_link_unauthorized(self, test_client, test_db):
        response = test_client.post(
            "/links/shorten",
            params={"original_url": "https://colab.research.google.com/drive/1_XpbChwNfdSu0k2cBItKDfAX3YOWxU3S?usp=sharing#scrollTo=hffGnSbyAr7i"}
        )
        assert response.status_code == 200
        assert response.json()["owner_id"] is None

    async def test_create_short_link_authorized(self, test_client, test_db, test_token):
        headers = {"Authorization": f"Bearer {test_token}"}
        response = test_client.post(
            "/links/shorten",
            params={
                "original_url": "https://anytask.org/issue/379604",
                "custom_alias": "auth-link"
            },
            headers=headers
        )

        assert response.status_code == 200

    async def test_create_duplicate_alias(self, test_client, test_db):
        response = test_client.post(
            "/links/shorten",
            params={
                "original_url": "https://duplicate.com",
                "custom_alias": "duplicate"
            }
        )
        assert response.status_code == 200

        response = test_client.post(
            "/links/shorten",
            params={
                "original_url": "https://another.com",
                "custom_alias": "duplicate"
            }
        )
        assert response.status_code == 400
        assert "Alias уже существует" in response.json()["detail"]


class TestRedirect:
    async def test_redirect_nonexistent_link(self, test_client):
        response = test_client.get("/links/nonexistent")
        assert response.status_code == 404
        assert "Ссылка не найдена" in response.json()["detail"]


class TestDeleteLink:
    async def test_delete_link_unauthorized(self, test_client, test_db):
        response = test_client.delete("/links/test123")
        assert response.status_code == 401

    async def test_delete_link_not_owner(self, test_client, test_db, test_token):
        # Создаем ссылку от другого пользователя
        test_client.post(
            "/links/shorten",
            params={"original_url": "https://delete-test.com", "custom_alias": "delete-test"}
        )

        headers = {"Authorization": f"Bearer {test_token}"}
        response = test_client.delete("/links/delete-test", headers=headers)
        assert response.status_code == 403

    async def test_delete_link_success(self, test_client, test_db, test_token):
        headers = {"Authorization": f"Bearer {test_token}"}
        test_client.post(
            "/links/shorten",
            params={"original_url": "https://success-delete.com", "custom_alias": "success-delete"},
            headers=headers
        )

        response = test_client.delete("/links/success-delete", headers=headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Ссылка успешно удалена"


class TestStatistics:
    async def test_get_stats(self, test_client, test_db):
        test_client.post(
            "/links/shorten",
            params={"original_url": "https://stats-test.com", "custom_alias": "stats-test"}
        )

        response = test_client.get("/links/stats-test/stats")
        assert response.status_code == 200
        assert response.json()["original_url"] == "https://stats-test.com"


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_by_url(self, test_client, test_db):
        test_url = "https://search-test.com"
        test_client.post(
            "/links/shorten",
            params={"original_url": test_url, "custom_alias": "search-alias"}
        )

        response = test_client.get(f"/links/url/search?original_url={test_url}")
        assert response.status_code == 200
        assert response.json()["short_code"] == "search-alias"


# Фикстура для очистки Redis
@pytest.fixture(autouse=True)
async def cleanup_redis():
    yield
    await redis.flushall()