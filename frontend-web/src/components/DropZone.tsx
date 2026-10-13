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
      className={`group/drop flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-[border-color,background-color,box-shadow] duration-200 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-glow-cyan ${
        over ? "border-glow-cyan bg-glow-cyan/[0.06] shadow-[0_0_0_4px_rgb(103_232_249/0.12)]" : "border-white/20 bg-white/[0.025] hover:border-white/35 hover:bg-white/[0.04]"
      }`}
    >
      <span className="grid size-12 place-items-center rounded-full border border-white/15 bg-[linear-gradient(135deg,rgb(67_97_238/0.35),rgb(139_92_246/0.25))] shadow-[0_8px_24px_-10px_rgb(67_97_238/0.8)] transition-transform duration-200 group-hover/drop:-translate-y-0.5">
        <FileUp aria-hidden className="size-5 text-white" />
      </span>
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
