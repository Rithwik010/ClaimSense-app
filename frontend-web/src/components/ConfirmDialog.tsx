// A confirmation before a step that cannot be undone (finalizing a claim). The native dialog
// element keeps the keyboard focus inside and closes on Escape.

import { useEffect, useRef, type ReactNode } from "react";

import { button } from "./ui";

export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) {
      if (typeof element.showModal === "function") element.showModal();
      else element.setAttribute("open", "");
    } else if (!open && element.open) {
      if (typeof element.close === "function") element.close();
      else element.removeAttribute("open");
    }
  }, [open]);
  return (
    <dialog
      ref={dialog}
      aria-labelledby="confirm-title"
      className="m-auto w-full max-w-md rounded-lg border border-gray-200 p-6 shadow-lg"
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
    >
      <h2 id="confirm-title" className="text-lg font-semibold">
        {title}
      </h2>
      <div className="mt-2 text-gray-700">{children}</div>
      <div className="mt-6 flex justify-end gap-3">
        <button type="button" className={button.secondary} onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className={button.primary} onClick={onConfirm} autoFocus>
          {confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
