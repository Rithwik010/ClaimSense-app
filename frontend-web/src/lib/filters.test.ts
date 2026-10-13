import { describe, expect, it } from "vitest";

import { ALL, count, matches, statusParam } from "./filters";
import { RETURNED_FILTERS, STAFF_FILTERS } from "./labels";

const CLAIM = {
  claim_id: "CLM-DEMO-04",
  member_id: "MBR-000123",
  provider_name: "Riverside Pain Clinic",
  provider_npi: "1234567893",
  outcome: "PARTLY_APPROVED" as const,
};

describe("claim list search and filter", () => {
  it("finds a reviewer's claim by claim ID, member ID, provider name or NPI, in part and any case", () => {
    for (const query of ["demo-04", "mbr-000123", "riverside", "PAIN clinic", "45678", "  CLM-DEMO  "]) {
      expect(matches(CLAIM, query, ALL, "all")).toBe(true);
    }
    expect(matches(CLAIM, "MBR-999", ALL, "all")).toBe(false);
  });

  it("searches a provider's claims by claim ID only", () => {
    expect(matches(CLAIM, "demo-04", ALL, "claim")).toBe(true);
    expect(matches(CLAIM, "riverside", ALL, "claim")).toBe(false);
  });

  it("combines the search with the status", () => {
    expect(matches(CLAIM, "demo", "PARTLY_APPROVED", "all")).toBe(true);
    expect(matches(CLAIM, "demo", "DENIED", "all")).toBe(false);
    expect(matches(CLAIM, "", ALL, "all")).toBe(true);
  });

  it("reads the status from the URL only when the page offers it", () => {
    expect(statusParam("DENIED", RETURNED_FILTERS)).toBe("DENIED");
    expect(statusParam("APPROVED", RETURNED_FILTERS)).toBe(ALL);
    expect(statusParam("NOT_PROCESSED", STAFF_FILTERS)).toBe("NOT_PROCESSED");
    expect(statusParam(null, STAFF_FILTERS)).toBe(ALL);
    expect(statusParam("nonsense", STAFF_FILTERS)).toBe(ALL);
  });

  it("counts claims in words", () => {
    expect(count(1)).toBe("1 claim");
    expect(count(12)).toBe("12 claims");
  });
});
