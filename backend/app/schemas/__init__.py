import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)


class RegisterIn(APIModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str

    @model_validator(mode="after")
    def validate_password(self):
        if self.password != self.password_confirmation:
            raise ValueError("Paroles nesakr?½t")
        if not re.search(r"[A-Z]", self.password) or not re.search(r"\d", self.password):
            raise ValueError("Parolei vajadz?½gs vismaz viens lielais burts un cipars")
        return self


class LoginIn(APIModel):
    email: EmailStr
    password: str


class UserOut(APIModel):
    id: int
    name: str
    email: EmailStr
    role: Literal["USER", "ADMIN"]
    is_active: bool
    created_at: datetime


class TokenOut(APIModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserUpdate(APIModel):
    role: Literal["USER", "ADMIN"] | None = None
    is_active: bool | None = None


class CategoryIn(APIModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=300)
    icon: str = Field(default="Package", max_length=30)
    color: Literal["blue", "green", "amber", "red", "purple"] = "blue"


class CategoryOut(CategoryIn):
    id: int
    item_count: int = 0
    created_at: datetime


class SupplierIn(APIModel):
    name: str = Field(min_length=3, max_length=150)
    contact_person: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(pattern=r"^[+\d\s()-]{7,30}$")
    address: str = Field(min_length=5, max_length=300)
    category: str = Field(default="Da?Š?üdi", max_length=100)
    payment_terms: Literal["net30", "net60", "cod"] = "net30"


class SupplierOut(SupplierIn):
    id: int
    is_active: bool
    created_at: datetime


class LocationIn(APIModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9-]+$")
    name: str = Field(min_length=2, max_length=120)
    capacity: int = Field(ge=1)


class LocationOut(LocationIn):
    id: int
    used_capacity: int = 0
    created_at: datetime


class ItemIn(APIModel):
    name: str = Field(min_length=3, max_length=100)
    sku: str = Field(min_length=3, max_length=30, pattern=r"^[A-Z0-9-]+$")
    category_id: int = Field(gt=0)
    supplier_id: int | None = None
    location_id: int = Field(gt=0)
    stock: int = Field(ge=0)
    min_stock: int = Field(ge=0)
    price: float = Field(ge=0)
    description: str = Field(default="", max_length=500)


class ItemUpdate(ItemIn):
    pass


class ItemOut(ItemIn):
    id: int
    category_name: str
    supplier_name: str | None
    location_name: str
    status: Literal["ok", "low", "critical"]
    created_at: datetime
    updated_at: datetime


class ItemList(APIModel):
    items: list[ItemOut]
    total: int
    page: int
    page_size: int


class TransferIn(APIModel):
    item_id: int = Field(gt=0)
    source_location_id: int = Field(gt=0)
    destination_location_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    priority: Literal["normal", "high", "urgent"] = "normal"
    notes: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def different_locations(self):
        if self.source_location_id == self.destination_location_id:
            raise ValueError("S?ükuma un galam?ōr?Ęa vieta nedr?½kst sakrist")
        return self


class TransferStatusIn(APIModel):
    status: Literal["pending", "in-transit", "done", "cancelled"]


class TransferOut(APIModel):
    id: int
    code: str
    item_id: int
    item_name: str
    source_location_id: int
    source_location_name: str
    destination_location_id: int
    destination_location_name: str
    quantity: int
    status: str
    priority: str
    notes: str
    creator_name: str
    created_at: datetime
    updated_at: datetime


class ActivityOut(APIModel):
    id: int
    message: str
    action: str
    entity_type: str
    user_name: str | None
    created_at: datetime

