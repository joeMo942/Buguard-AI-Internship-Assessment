import pytest
from app.models.asset import Asset
from sqlalchemy.future import select

@pytest.mark.asyncio
async def test_create_asset(db_session):
    new_asset = Asset(
        id="test-1",
        type="domain",
        value="test.com",
        status="active",
        source="scan"
    )
    db_session.add(new_asset)
    await db_session.commit()

    stmt = select(Asset).where(Asset.id == "test-1")
    result = await db_session.execute(stmt)
    saved_asset = result.scalar_one_or_none()

    assert saved_asset is not None
    assert saved_asset.value == "test.com"
    assert saved_asset.type == "domain"
    assert saved_asset.status == "active"
