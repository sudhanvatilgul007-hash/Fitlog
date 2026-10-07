import { describe, it, expect, vi, afterEach } from "vitest";
import { scaled, api, localDate } from "./api";
afterEach(() => vi.unstubAllGlobals());
describe("food quantity previews", () => {
  it("uses per-base nutrition", () => {
    expect(
      scaled({ baseQuantity: 100, calories: 639, proteinG: 30 }, 20),
    ).toEqual({ calories: 127.8, proteinG: 6 });
  });
  it("scales slices", () => {
    expect(scaled({ baseQuantity: 1, calories: 58, proteinG: 6.5 }, 2)).toEqual(
      { calories: 116, proteinG: 13 },
    );
  });
});
it("surfaces server errors rather than accepting failed mutations", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Quantity must be positive" }),
      }),
  );
  await expect(api("/foods", "POST", {})).rejects.toThrow(
    "Quantity must be positive",
  );
});
it("uses local calendar dates", () => {
  expect(localDate()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});
