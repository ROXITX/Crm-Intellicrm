import { describe, expect, it } from "vitest";
import { ago, initials, money, pct, title } from "@/lib/format";

describe("format helpers", () => {
  it("formats rupees without decimals", () => expect(money("103840")).toContain("1,03,840"));
  it("handles nulls", () => { expect(money(null)).toBe("-"); expect(pct(null)).toBe("-"); expect(title(null)).toBe("-"); });
  it("formats probabilities", () => expect(pct(0.82)).toBe("82%"));
  it("title-cases snake_case", () => expect(title("waiting_customer")).toBe("Waiting Customer"));
  it("initials", () => expect(initials("Rohit Sharma")).toBe("RS"));
  it("relative time handles past and future", () => {
    expect(ago(new Date(Date.now() - 3 * 86400e3).toISOString())).toBe("3 d ago");
    expect(ago(new Date(Date.now() + 2 * 86400e3 + 5000).toISOString())).toBe("in 2 d");
    expect(ago(null)).toBe("never");
  });
});
