// "View original file" (D-DOC-1): the file a claim was filed from, in a wide side sheet. A PDF in
// the browser's own viewer, an image fitted to the width with zoom, a JSON claim pretty-printed in a
// monospace font; "Open in new tab" opens the same file. Everything comes from the API on the app's
// own origin (GET /v1/claims/{id}/document); no outside viewer.

import { useQuery } from "@tanstack/react-query";
import { ExternalLink, FileText, Minus, Plus } from "lucide-react";
import { useState } from "react";

import { request } from "@/api/client";
import type { DocumentInfo } from "@/api/types";
import { ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

const KINDS: Record<DocumentInfo["content_type"], string> = {
  "application/json": "JSON claim",
  "application/pdf": "PDF",
  "image/png": "PNG image",
  "image/jpeg": "JPEG image",
};
const ZOOMS = [1, 1.5, 2, 3];

export function documentUrl(claimId: string): string {
  return `/v1/claims/${encodeURIComponent(claimId)}/document`;
}

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${Math.round((bytes / (1024 * 1024)) * 10) / 10} MB`;
}

function JsonFile({ url }: { url: string }) {
  const file = useQuery({
    queryKey: ["document", url],
    queryFn: () => request<string>(url, { expect: "text" }),
  });
  if (file.isPending) return <Skeleton lines={8} />;
  if (file.error) return <ErrorNotice error={file.error} onRetry={() => void file.refetch()} />;
  let text = file.data;
  try {
    text = JSON.stringify(JSON.parse(file.data), null, 2);
  } catch {
    // Shown as it was sent.
  }
  return (
    <pre
      data-testid="original-json"
      className="min-h-0 flex-1 overflow-auto rounded-md border border-rules bg-black/30 p-4 font-mono text-[13px] leading-5 whitespace-pre"
      tabIndex={0}
    >
      {text}
    </pre>
  );
}

function ImageFile({ url, name }: { url: string; name: string }) {
  const [zoom, setZoom] = useState(0);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center gap-2" role="group" aria-label="Zoom">
        <Button variant="outline" size="sm" disabled={zoom === 0} onClick={() => setZoom((z) => z - 1)}>
          <Minus aria-hidden /> Zoom out
        </Button>
        <Button variant="outline" size="sm" disabled={zoom === ZOOMS.length - 1} onClick={() => setZoom((z) => z + 1)}>
          <Plus aria-hidden /> Zoom in
        </Button>
        <span className="text-[13px] text-ink-muted tabular-nums" aria-live="polite">
          {zoom === 0 ? "Fit to width" : `${(ZOOMS[zoom] ?? 1) * 100}% of the width`}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto rounded-md border border-rules bg-white" tabIndex={0}>
        <img
          src={url}
          alt={`Original file: ${name}`}
          className="block max-w-none"
          style={{ width: `${(ZOOMS[zoom] ?? 1) * 100}%` }}
        />
      </div>
    </div>
  );
}

export function OriginalFileButton({ claimId, document }: { claimId: string; document: DocumentInfo | null }) {
  const [open, setOpen] = useState(false);
  const url = documentUrl(claimId);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="lg">
          <FileText aria-hidden /> View original file
        </Button>
      </SheetTrigger>
        <SheetContent className="w-full gap-3 data-[side=right]:w-full data-[side=right]:sm:max-w-3xl">
          <SheetHeader className="px-6 pt-6 pb-0">
            <SheetTitle className="pr-8 text-[18px] font-semibold">Original file</SheetTitle>
            <SheetDescription className="break-all text-ink-muted">
              {document
                ? `${document.file_name} · ${KINDS[document.content_type]} · ${size(document.size_bytes)}`
                : `Claim ${claimId}`}
            </SheetDescription>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col gap-3 px-6 pb-6">
            {document ? (
              <>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener"
                  className="inline-flex w-fit items-center gap-1.5 text-[14px] font-semibold text-link underline-offset-4 hover:text-white hover:underline"
                >
                  Open in new tab <ExternalLink aria-hidden className="size-3.5" />
                </a>
                {document.content_type === "application/pdf" ? (
                  <iframe
                    title={`Original file: ${document.file_name}`}
                    src={url}
                    className="min-h-[60vh] w-full flex-1 rounded-md border border-rules bg-white"
                  />
                ) : document.content_type === "application/json" ? (
                  <JsonFile url={url} />
                ) : (
                  <ImageFile url={url} name={document.file_name} />
                )}
              </>
            ) : (
              <p className="rounded-md border border-dashed border-white/15 px-4 py-10 text-center text-ink-muted">
                Original file not available
              </p>
            )}
          </div>
        </SheetContent>
    </Sheet>
  );
}
