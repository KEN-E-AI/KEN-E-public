from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    """Base model for items."""

    name: str = Field(..., description="The name of the item")
    description: str | None = Field(None, description="Description of the item")
    price: float = Field(..., gt=0, description="Price must be greater than 0")


class ItemCreate(ItemBase):
    """Model for creating items."""

    pass


class ItemResponse(ItemBase):
    """Model for item responses."""

    id: int = Field(..., description="Unique identifier for the item")

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    """Model for health check responses."""

    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )
