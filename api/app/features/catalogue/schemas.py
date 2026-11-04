import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Public listings must never show exact room numbers ("Room 204", "rm B12", "block C room 7").
_ROOM = re.compile(r"\b(room|rm|rm\.|flat|apartment|apt)\s*(no\.?|number|#)?\s*[a-z]?\d{1,4}[a-z]?\b", re.IGNORECASE)


def contains_room_number(text: str) -> bool:
    return bool(_ROOM.search(text))


class VariantIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    options: list[str] = Field(min_length=1, max_length=12)


class PackageIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    price_kobo: int = Field(gt=0)
    description: str = Field(default="", max_length=300)


class ListingIn(BaseModel):
    type: Literal["product", "service"]
    category_id: int
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(default="", max_length=4000)
    price_kobo: int = Field(gt=0, le=1_000_000_000)
    price_max_kobo: int | None = Field(default=None, gt=0)
    negotiable: bool = False
    location_id: int | None = None
    publish: bool = True
    # products
    condition: Literal["new", "like_new", "used"] | None = None
    quantity: int = Field(default=1, ge=0, le=10_000)
    variants: list[VariantIn] = Field(default_factory=list, max_length=4)
    fulfilment: Literal["pickup", "delivery", "both"] = "pickup"
    delivery_fee_kobo: int = Field(default=0, ge=0)
    preorder: bool = False
    # services
    availability: str | None = Field(default=None, max_length=200)
    duration_min: int | None = Field(default=None, gt=0, le=1440)
    deposit_kobo: int | None = Field(default=None, gt=0)
    packages: list[PackageIn] = Field(default_factory=list, max_length=6)

    @field_validator("title", "description")
    @classmethod
    def _no_room_numbers(cls, v: str) -> str:
        if contains_room_number(v):
            raise ValueError("Do not include exact room numbers. Use the hall or area instead.")
        return v

    @model_validator(mode="after")
    def _check(self) -> "ListingIn":
        if self.price_max_kobo is not None and self.price_max_kobo < self.price_kobo:
            raise ValueError("The highest price must be at least the starting price")
        if self.type == "product" and self.condition is None:
            raise ValueError("Choose a condition for products")
        if self.deposit_kobo is not None and self.deposit_kobo > self.price_kobo:
            raise ValueError("The booking deposit cannot be more than the price")
        return self


class ListingPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=140)
    description: str | None = Field(default=None, max_length=4000)
    price_kobo: int | None = Field(default=None, gt=0, le=1_000_000_000)
    price_max_kobo: int | None = Field(default=None, gt=0)
    negotiable: bool | None = None
    location_id: int | None = None
    category_id: int | None = None
    condition: Literal["new", "like_new", "used"] | None = None
    quantity: int | None = Field(default=None, ge=0, le=10_000)
    fulfilment: Literal["pickup", "delivery", "both"] | None = None
    delivery_fee_kobo: int | None = Field(default=None, ge=0)
    availability: str | None = Field(default=None, max_length=200)
    deposit_kobo: int | None = Field(default=None, gt=0)

    @field_validator("title", "description")
    @classmethod
    def _no_room_numbers(cls, v: str | None) -> str | None:
        if v and contains_room_number(v):
            raise ValueError("Do not include exact room numbers. Use the hall or area instead.")
        return v


class StatusIn(BaseModel):
    status: Literal["active", "paused", "sold_out", "removed"]


class ShopStartIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    bio: str = Field(default="", max_length=600)
    location_id: int | None = None
    vendor_type: Literal["student", "vendor"] = "student"
    accept_rules: bool


class ShopSettingsIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    bio: str | None = Field(default=None, max_length=600)
    location_id: int | None = None
    holiday_mode: bool | None = None
    payout_bank: str | None = Field(default=None, min_length=2, max_length=60)
    payout_account_number: str | None = Field(default=None, pattern=r"^\d{10}$")
    payout_account_name: str | None = Field(default=None, min_length=2, max_length=120)


class SellerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    public_id: str
    slug: str
    name: str
    bio: str
    verification_status: str
    trust_level: str
    holiday_mode: bool
    confirmed_deals: int
    rating_count: int
    rating_avg: float | None = None
    location_name: str | None = None
    campus_name: str | None = None
    vouched_by_rep: bool = False


class ImageOut(BaseModel):
    id: int
    url: str


class ListingCard(BaseModel):
    public_id: str
    title: str
    type: str
    price_kobo: int
    price_max_kobo: int | None
    category_slug: str
    category_tint: str
    location_name: str | None
    image_url: str | None
    seller_name: str
    seller_slug: str
    seller_verified: bool
    rating_avg: float | None
    sponsored: bool = False
    status: str


class ListingDetail(ListingCard):
    description: str
    negotiable: bool
    condition: str | None
    quantity: int
    variants: list[dict]
    fulfilment: str
    delivery_fee_kobo: int
    preorder: bool
    availability: str | None
    duration_min: int | None
    deposit_kobo: int | None
    packages: list[dict]
    images: list[ImageOut]
    seller: SellerOut
    expires_at: str | None
    created_at: str
    campus_name: str | None


class ListingPage(BaseModel):
    items: list[ListingCard]
    total: int
    page: int
    size: int


class PayoutPreview(BaseModel):
    buyer_price_kobo: int
    commission_bps: int
    commission_kobo: int
    seller_payout_kobo: int
