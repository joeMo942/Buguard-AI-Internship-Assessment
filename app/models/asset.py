from sqlalchemy import Column, String, Enum, DateTime, JSON, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.models.base import Base

class Asset(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(String, nullable=False, index=True, default="default")
    type = Column(Enum('domain', 'subdomain', 'ip_address', 'service', 'certificate', 'technology', name='asset_type'), nullable=False)
    value = Column(String, nullable=False, index=True)
    status = Column(Enum('active', 'stale', 'archived', name='asset_status'), nullable=False, default='active')
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    source = Column(String, nullable=False)
    tags = Column(JSON, default=list) # Using JSON for simpler array handling on SQLite/Postgres across dev
    metadata_ = Column(JSON, default=dict)

    __table_args__ = (
        UniqueConstraint('org_id', 'type', 'value', name='uq_org_asset_type_value'),
        Index('ix_assets_type', 'type'),
        Index('ix_assets_status', 'status'),
        Index('ix_assets_org_type_status', 'org_id', 'type', 'status'),
    )
