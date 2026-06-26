from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
import uuid
from app.models.base import Base

def generate_uuid():
    return str(uuid.uuid4())

class AssetRelationship(Base):
    __tablename__ = "asset_relationships"

    id = Column(String, primary_key=True, default=generate_uuid)
    org_id = Column(String, nullable=False, index=True, default="default")
    source_asset_id = Column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    target_asset_id = Column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint('source_asset_id', 'target_asset_id', 'relationship_type', name='uq_asset_relationship'),
    )
