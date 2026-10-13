import { describe, expect, it } from "vitest";

import { age, basisPoints, money, percent } from "./format";

describe("amounts", () => {
  it.each<[number | null | undefined, string]>([
    [0, "$0.00"],
    [5, "$0.05"],
    [12345, "$123.45"],
    [9639, "$96.39"],
    [100000, "$1,000.00"],
    [123456789, "$1,234,567.89"],
    [-1050, "-$10.50"],
    [null, "—"],
    [undefined, "—"],
  ])("formats %s cents as %s, with integer arithmetic only", (cents, shown) => {
    expect(money(cents)).toBe(shown);
  });

  it("never rounds through floating point", () => {
    // 0.1 + 0.2 style errors cannot happen: cents stay integers until they are printed.
    expect(money(30)).toBe("$0.30");
    expect(money(1_000_000_001)).toBe("$10,000,000.01");
  });
});

describe("shares and ages", () => {
  it("shows a share as a percentage with one decimal", () => {
    expect(percent(0.98)).toBe("98.0%");
    expect(percent(0.9378)).toBe("93.8%");
  });

  it("shows how long ago in the largest whole unit", () => {
    const now = new Date("2026-10-11T12:00:00Z");
    expect(age("2026-10-11T11:55:00Z", now)).toBe("5 min");
    expect(age("2026-10-11T09:00:00Z", now)).toBe("3 h");
    expect(age("2026-10-09T12:00:00Z", now)).toBe("2 d");
    expect(age(null, now)).toBe("—");
  });
});

describe("rates in basis points", () => {
  it.each<[number | null, string]>([
    [2000, "20%"],
    [2050, "20.5%"],
    [1255, "12.55%"],
    [0, "0%"],
    [10000, "100%"],
    [null, "—"],
  ])("shows %s bps as %s", (bps, shown) => {
    expect(basisPoints(bps)).toBe(shown);
  });
});
