from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException

from ..models.schemas import ItemCreate, ItemResponse

router = APIRouter(
    prefix="/api/v1/items",
    tags=["items"],
    responses={404: {"description": "Not found"}},
)

# In-memory storage for demo purposes
fake_items_db = []
item_id_counter = 1


@router.post("/", response_model=ItemResponse, status_code=201)
async def create_item(item: ItemCreate):
    """
    Create a new item.
    """
    global item_id_counter
    new_item = ItemResponse(
        id=item_id_counter,
        name=item.name,
        description=item.description,
        price=item.price,
    )
    fake_items_db.append(new_item)
    item_id_counter += 1
    return new_item


@router.get("/", response_model=List[ItemResponse])
async def get_items():
    """
    Retrieve all items.
    """
    return fake_items_db


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int):
    """
    Retrieve a specific item by ID.
    """
    for item in fake_items_db:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(item_id: int, item_update: ItemCreate):
    """
    Update an existing item.
    """
    for i, item in enumerate(fake_items_db):
        if item.id == item_id:
            updated_item = ItemResponse(
                id=item_id,
                name=item_update.name,
                description=item_update.description,
                price=item_update.price,
            )
            fake_items_db[i] = updated_item
            return updated_item
    raise HTTPException(status_code=404, detail="Item not found")


@router.delete("/{item_id}")
async def delete_item(item_id: int):
    """
    Delete an item.
    """
    for i, item in enumerate(fake_items_db):
        if item.id == item_id:
            del fake_items_db[i]
            return {"message": "Item deleted successfully"}
    raise HTTPException(status_code=404, detail="Item not found")
