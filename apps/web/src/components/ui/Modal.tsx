"use client";

import { useEffect, useRef, type ReactNode } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  labelledBy: string;
  className: string;
  children: ReactNode;
}

export default function Modal({ open, onClose, labelledBy, className, children }: Readonly<ModalProps>) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    dialog.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  return (
    <dialog ref={dialogRef} aria-labelledby={labelledBy} onCancel={onClose}
      className="fixed inset-0 m-0 h-dvh max-h-none w-screen max-w-none border-0 bg-transparent p-0 text-slate-200 backdrop:bg-black/70">
      <div className="flex h-full items-end justify-center sm:items-center sm:p-6">
        <button type="button" aria-label="Close details" onClick={onClose}
          className="absolute inset-0 cursor-default" />
        <div className={`relative ${className}`}>{children}</div>
      </div>
    </dialog>
  );
}
