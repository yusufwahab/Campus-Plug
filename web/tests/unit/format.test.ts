import { naira, priceRange, timeAgo } from "@/lib/format";

describe("format", () => {
  it("formats kobo as naira", () => {
    expect(naira(1000000)).toBe("₦10,000");
    expect(naira(1050)).toBe("₦10.50");
  });
  it("formats ranges", () => {
    expect(priceRange(100000, 250000)).toBe("₦1,000 - ₦2,500");
    expect(priceRange(100000)).toBe("₦1,000");
  });
  it("formats relative time", () => {
    const now = Date.parse("2026-01-01T12:00:00Z");
    expect(timeAgo("2026-01-01T11:30:00Z", now)).toBe("30m ago");
    expect(timeAgo("2025-12-30T12:00:00Z", now)).toBe("2d ago");
  });
});
