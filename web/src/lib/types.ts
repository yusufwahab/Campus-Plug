import type { components } from "./api-schema";

type S = components["schemas"];

export type User = S["UserOut"];
export type TokenOut = S["TokenOut"];
export type ListingCardData = S["ListingCard"];
export type ListingDetail = S["ListingDetail"];
export type Seller = S["SellerOut"];
