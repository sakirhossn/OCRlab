"""
Bootstrap / Seed Script for Unlimited OCR Cloud.

Initializes the database, creates a default organization / tenant,
and generates an active API key for immediate local development and testing.
"""

import asyncio
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import AsyncSessionLocal, init_db
from app.core.security import generate_api_key, hash_secret
from app.models.tenant import APIKey, Tenant, User
from sqlalchemy import select


async def bootstrap() -> None:
    print("==> Initializing Database Tables...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # Check if demo tenant already exists
        stmt = select(Tenant).where(Tenant.slug == "demo-enterprise")
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()

        if not tenant:
            print("==> Creating Demo Organization: 'Demo Enterprise'...")
            tenant = Tenant(
                name="Demo Enterprise",
                slug="demo-enterprise",
                monthly_page_quota=5000,
            )
            session.add(tenant)
            await session.flush()

            user = User(
                tenant_id=tenant.id,
                email="admin@demo.com",
                hashed_password=hash_secret("DemoAdminPassword123!"),
                full_name="Demo Administrator",
                role="owner",
            )
            session.add(user)
            await session.flush()

            # Generate default API Key
            raw_key, prefix, hashed = generate_api_key()
            api_key = APIKey(
                tenant_id=tenant.id,
                name="Default Development Key",
                key_prefix=prefix,
                hashed_key=hashed,
                rate_limit_rpm=120,
            )
            session.add(api_key)
            await session.commit()

            print("\n" + "=" * 64)
            print("  UNLIMITED OCR CLOUD — LOCAL BOOTSTRAP COMPLETE")
            print("=" * 64)
            print(f"  Tenant Name:   {tenant.name}")
            print(f"  Tenant ID:     {tenant.id}")
            print(f"  Monthly Quota: {tenant.monthly_page_quota} pages")
            print(f"  API KEY:       {raw_key}")
            print("=" * 64)
            print("\n  SAVE THIS API KEY! Use it in Authorization header:")
            print(f'  Authorization: Bearer {raw_key}\n')
            print("  Test Upload with cURL:")
            print(f'  curl -X POST http://localhost:8000/v1/documents \\')
            print(f'       -H "Authorization: Bearer {raw_key}" \\')
            print(f'       -F "file=@sample.pdf"\n')
            print("  Test with Python SDK:")
            print(f'  from unlimited_ocr import UnlimitedOCRClient')
            print(f'  client = UnlimitedOCRClient(base_url="http://localhost:8000", api_key="{raw_key}")\n')
        else:
            print(f"==> Demo tenant already exists (ID: {tenant.id}).")


if __name__ == "__main__":
    asyncio.run(bootstrap())
