# backend/app/schemas.py
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


# ---------- MATERIALS ----------
class CustomStatus(BaseModel):
    permalink: str
    title: str

    model_config = {
        "from_attributes": True
    }


class MaterialBase(BaseModel):
    name: str
    unit: str = "шт"
    base_qty: float = 0.0
    min_qty: float = 0.0

    model_config = {
        "from_attributes": True
    }


class MaterialCreate(MaterialBase):
    pass


class Material(MaterialBase):
    id: int

    model_config = {
        "from_attributes": True
    }


# ---------- MATERIAL RULES ----------

class MaterialRuleBase(BaseModel):
    pattern: str
    material_id: int
    qty: float = 1.0

    model_config = {
        "from_attributes": True
    }


class MaterialRuleCreate(MaterialRuleBase):
    pass


class MaterialRule(MaterialRuleBase):
    id: int
    material: Material

    model_config = {
        "from_attributes": True
    }


# ---------- ORDER LINES ----------

class OrderLine(BaseModel):
    product_id: int
    product_title: str
    quantity: int

    model_config = {
        "from_attributes": True
    }


# ---------- ORDERS ----------

class OrderOut(BaseModel):
    id: int
    number: str
    customer: Optional[str] = None
    created_at: datetime
    ignored: bool = False
    ready_notified: bool = False
    client_notified: bool = False
    custom_status: Optional[CustomStatus] = None
    lines: List[OrderLine] = []

    @field_validator("number", mode="before")
    @classmethod
    def _ensure_str_number(cls, v):
        return str(v)

    model_config = {"from_attributes": True}


# ---------- READY FILMS ----------

class FilmOut(BaseModel):
    title: str
    quantity: int

    model_config = {
        "from_attributes": True
    }
