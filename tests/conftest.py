"""Test configuration and fixtures using in-memory SQLite and async httpx client."""

import io
from typing import AsyncGenerator
import pymupdf
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.api.deps import get_db
from app.core.database import Base
from app.core.security import generate_api_key
from app.main import app
from app.models.tenant import APIKey, Tenant

# In-memory SQLite database for test suite isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_tenant_and_key(db_session: AsyncSession):
    tenant = Tenant(
        name="Acme Corp",
        slug="acme-corp",
        tier="pro",
        monthly_page_quota=500,
    )
    db_session.add(tenant)
    await db_session.flush()

    raw_key, prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        tenant_id=tenant.id,
        name="Production Key",
        key_prefix=prefix,
        hashed_key=hashed_key,
        rate_limit_rpm=120,
        monthly_quota=500,
    )
    db_session.add(api_key)
    await db_session.commit()

    return tenant, api_key, raw_key


@pytest.fixture
def make_pdf_bytes():
    """Factory fixture creating real PDF bytes with text and tables using PyMuPDF."""
    def _create_pdf(pages: int = 1, text: str = "Standard digital document content.") -> bytes:
        doc = pymupdf.open()
        for i in range(pages):
            page = doc.new_page(width=612, height=792)
            page.insert_text((50, 72), f"Page {i+1} Title", fontsize=16)
            page.insert_text((50, 100), f"{text} (Iteration {i+1})", fontsize=11)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    return _create_pdf
