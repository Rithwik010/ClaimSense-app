import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DocumentInfo } from "../api/types";
import { arrange, DropZone } from "./DropZone";
import { OriginalFileButton } from "./OriginalFile";

const file = (name: string, type = "image/png") => new File(["x"], name, { type });

describe("a claim in several files (D-DOC-2)", () => {
  it("keeps the pages in name order", () => {
    const { files, note } = arrange([file("scan-2.png"), file("scan-1.png")]);
    expect(files.map((f) => f.name)).toEqual(["scan-1.png", "scan-2.png"]);
    expect(note).toBeNull();
    expect(arrange([file("page 10.png"), file("page 9.png")]).files.map((f) => f.name)).toEqual([
      "page 9.png",
      "page 10.png",
    ]);
  });

  it("keeps five files at most: a claim form has at most five pages (D-DOC-3)", () => {
    const six = ["p6", "p3", "p1", "p5", "p2", "p4"].map((name) => file(`${name}.png`));
    const { files, note } = arrange(six);
    expect(files.map((f) => f.name)).toEqual(["p1.png", "p2.png", "p3.png", "p4.png", "p5.png"]);
    expect(note).toMatch(/at most 5 pages/);
  });

  it("accepts five files, in page order (D-DOC-3)", () => {
    const { files, note } = arrange(["p5", "p4", "p3", "p2", "p1"].map((name) => file(`${name}.png`)));
    expect(files.map((f) => f.name)).toEqual(["p1.png", "p2.png", "p3.png", "p4.png", "p5.png"]);
    expect(note).toBeNull();
  });

  it("offers to add the next page until five, and lists three pages without a swap (D-DOC-3)", () => {
    const three = [file("a.png"), file("b.png"), file("c.png")];
    const { rerender } = render(<DropZone files={three} onFiles={() => {}} />);
    expect(screen.getByLabelText("Page 4 file")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Files chosen, in page order" })).toHaveTextContent("Page 3c.png");
    expect(screen.queryByRole("button", { name: "Swap pages" })).toBeNull();
    rerender(<DropZone files={[...three, file("d.png"), file("e.png")]} onFiles={() => {}} />);
    expect(screen.queryByLabelText("Page 6 file")).toBeNull();
  });

  it("keeps a JSON claim on its own", () => {
    const { files, note } = arrange([file("claim.json", "application/json"), file("p2.png")]);
    expect(files.map((f) => f.name)).toEqual(["claim.json"]);
    expect(note).toMatch(/whole claim/);
  });

  it("lists two files as page 1 and page 2, and swaps them", async () => {
    const onFiles = vi.fn();
    render(<DropZone files={[file("a.png"), file("b.png")]} onFiles={onFiles} />);

    const list = screen.getByRole("list", { name: "Files chosen, in page order" });
    expect(list).toHaveTextContent("Page 1a.png");
    expect(list).toHaveTextContent("Page 2b.png");
    await userEvent.click(screen.getByRole("button", { name: "Swap pages" }));
    expect(onFiles.mock.calls[0]![0].map((f: File) => f.name)).toEqual(["b.png", "a.png"]);
  });

  it("offers to add page 2 after one page, not after a JSON claim", () => {
    const { rerender } = render(<DropZone files={[file("a.png")]} onFiles={() => {}} />);
    expect(screen.getByLabelText("Page 2 file")).toBeInTheDocument();
    rerender(<DropZone files={[file("c.json", "application/json")]} onFiles={() => {}} />);
    expect(screen.queryByLabelText("Page 2 file")).toBeNull();
  });

  it("shows each kept file of a claim in turn", async () => {
    const documents: DocumentInfo[] = [
      { file_no: 1, file_name: "p1.pdf", content_type: "application/pdf", size_bytes: 2048 },
      { file_no: 2, file_name: "p2.pdf", content_type: "application/pdf", size_bytes: 1024 },
    ];
    render(<OriginalFileButton claimId="CLM-1" documents={documents} />);

    await userEvent.click(screen.getByRole("button", { name: "View original files" }));
    expect(screen.getByTitle("Original file: p1.pdf")).toHaveAttribute("src", "/v1/claims/CLM-1/document/1");
    await userEvent.click(screen.getByRole("button", { name: "File 2" }));
    expect(screen.getByTitle("Original file: p2.pdf")).toHaveAttribute("src", "/v1/claims/CLM-1/document/2");
    expect(screen.getByRole("button", { name: "File 2" })).toHaveAttribute("aria-pressed", "true");
  });
});
