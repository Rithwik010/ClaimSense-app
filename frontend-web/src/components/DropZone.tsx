// A file drop zone: drag a claim file onto it, or click to choose one. The file input stays in
// the page (labelled "Claim file") so a keyboard and the browser's own picker work too.

import { FileUp } from "lucide-react";
import { useId, useRef, useState } from "react";

const ACCEPT =
  ".json,.pdf,.png,.jpg,.jpeg,.tif,.tiff,application/json,application/pdf,image/*";

export function DropZone({ file, onFile }: { file: File | null; onFile: (file: File | null) => void }) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
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
        const dropped = event.dataTransfer.files[0];
        if (dropped) onFile(dropped);
      }}
      className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-ink ${
        over ? "border-ink bg-canvas" : "border-control/70 bg-paper"
      }`}
    >
      <FileUp aria-hidden className="size-6 text-ink-muted" />
      <span className="font-semibold">{file ? file.name : "Drop a claim file here, or choose one"}</span>
      <span className="text-[13px] text-ink-muted">
        {file
          ? `${Math.max(1, Math.round(file.size / 1024))} KB. Drop another file to replace it.`
          : "A JSON claim, a PDF of the ClaimSense form, or a scanned form (PDF, PNG, JPEG or TIFF)."}
      </span>
      <input
        ref={input}
        id={id}
        type="file"
        aria-label="Claim file"
        accept={ACCEPT}
        className="sr-only"
        onChange={(event) => onFile(event.target.files?.[0] ?? null)}
      />
    </label>
  );
}
