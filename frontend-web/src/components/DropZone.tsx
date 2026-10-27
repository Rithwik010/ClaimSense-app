// A file drop zone: drag a claim file onto it, or click to choose one. The file input stays in
// the page (labelled "Claim file") so a keyboard and the browser's own picker work too. A claim's
// form can also come as its pages in several files (D-DOC-2; up to 5 when its notes go on to
// continuation pages, D-DOC-3): choose or drop them all, or add the next page after the ones chosen;
// they are listed in page order (by name at first), with a button to swap two pages.

import { ArrowUpDown, FilePlus2, FileUp, X } from "lucide-react";
import { useId, useRef, useState } from "react";

import { MAX_CLAIM_FILES } from "@/api/hooks";
import { Button } from "@/components/ui/button";

const ACCEPT =
  ".json,.pdf,.png,.jpg,.jpeg,.tif,.tiff,application/json,application/pdf,image/*";
const PAGE_ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";

const isJson = (file: File) => file.type === "application/json" || file.name.toLowerCase().endsWith(".json");
const byName = (a: File, b: File) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
const kb = (file: File) => `${Math.max(1, Math.round(file.size / 1024))} KB`;

/** The files to keep from a choice, in page order, and why any were left out. */
export function arrange(chosen: File[]): { files: File[]; note: string | null } {
  const sorted = [...chosen].sort(byName);
  const json = sorted.find(isJson);
  if (json && sorted.length > 1) {
    return { files: [json], note: "A JSON claim is the whole claim, so it was kept on its own." };
  }
  if (sorted.length > MAX_CLAIM_FILES) {
    return {
      files: sorted.slice(0, MAX_CLAIM_FILES),
      note: `Only the first ${MAX_CLAIM_FILES} files were kept: a claim form has at most ${MAX_CLAIM_FILES} pages.`,
    };
  }
  return { files: sorted, note: null };
}

export function DropZone({ files, onFiles }: { files: File[]; onFiles: (files: File[]) => void }) {
  const id = useId();
  const addId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const choose = (chosen: File[]) => {
    const kept = arrange(chosen);
    setNote(kept.note);
    onFiles(kept.files);
  };
  const [first] = files;
  const several = files.length > 1;
  return (
    <div className="space-y-3">
      <label
        htmlFor={id}
        onDragOver={(event) => {
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setOver(false);
          const dropped = Array.from(event.dataTransfer.files);
          if (dropped.length) choose(dropped);
        }}
        className={`group/drop flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-[border-color,background-color,box-shadow] duration-200 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-glow-cyan ${
          over ? "border-glow-cyan bg-glow-cyan/[0.06] shadow-[0_0_0_4px_rgb(103_232_249/0.12)]" : "border-white/20 bg-white/[0.025] hover:border-white/35 hover:bg-white/[0.04]"
        }`}
      >
        <span className="grid size-12 place-items-center rounded-full border border-white/15 bg-[linear-gradient(135deg,rgb(67_97_238/0.35),rgb(139_92_246/0.25))] shadow-[0_8px_24px_-10px_rgb(67_97_238/0.8)] transition-transform duration-200 group-hover/drop:-translate-y-0.5">
          <FileUp aria-hidden className="size-5 text-white" />
        </span>
        <span className="font-semibold">
          {several ? `${files.length} files: one claim, in page order` : first ? first.name : "Drop a claim file here, or choose one"}
        </span>
        <span className="max-w-[60ch] text-[13px] text-ink-muted">
          {first
            ? several
              ? "Drop or choose files again to replace them."
              : `${kb(first)}. Drop another file to replace it.`
            : `A JSON claim, a PDF of the ClaimSense form, or a scanned form (PDF, PNG, JPEG or TIFF). A form's pages can be separate files, up to ${MAX_CLAIM_FILES}: choose or drop them all.`}
        </span>
        <input
          ref={input}
          id={id}
          type="file"
          multiple
          aria-label="Claim file"
          accept={ACCEPT}
          className="sr-only"
          onChange={(event) => {
            choose(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
      </label>
      {note && (
        <p role="status" className="text-[13px] text-pend">
          {note}
        </p>
      )}
      {several && (
        <div className="surface rounded-lg px-4 py-3">
          <ol aria-label="Files chosen, in page order" className="divide-y divide-rules">
            {files.map((file, i) => (
              <li key={`${file.name}-${i}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
                <span className="w-14 shrink-0 text-[13px] font-semibold text-ink-muted">Page {i + 1}</span>
                <span className="min-w-0 flex-1 break-all">{file.name}</span>
                <span className="text-[13px] text-ink-muted tabular-nums">{kb(file)}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove ${file.name}`}
                  onClick={() => {
                    setNote(null);
                    onFiles(files.filter((_, j) => j !== i));
                  }}
                >
                  <X aria-hidden /> Remove
                </Button>
              </li>
            ))}
          </ol>
          {files.length === 2 && (
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() => {
                setNote(null);
                onFiles([...files].reverse());
              }}
            >
              <ArrowUpDown aria-hidden /> Swap pages
            </Button>
          )}
        </div>
      )}
      {files.length >= 1 && files.length < MAX_CLAIM_FILES && first && !isJson(first) && (
        <div>
          <input
            id={addId}
            type="file"
            aria-label={`Page ${files.length + 1} file`}
            accept={PAGE_ACCEPT}
            className="peer sr-only"
            onChange={(event) => {
              const added = event.target.files?.[0];
              event.target.value = "";
              if (added) {
                setNote(null);
                onFiles([...files, added]);
              }
            }}
          />
          <label
            htmlFor={addId}
            className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md border border-white/15 bg-white/[0.04] px-3 text-[13px] font-medium transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-glow-cyan hover:bg-white/[0.08]"
          >
            <FilePlus2 aria-hidden className="size-4" /> Add page {files.length + 1} as another file
          </label>
        </div>
      )}
    </div>
  );
}
