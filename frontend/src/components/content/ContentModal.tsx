'use client';

import {
  useEffect,
  useRef,
  useCallback,
  type ReactNode,
  type KeyboardEvent,
} from 'react';
import { X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ContentModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  /** The element that triggered the modal — focus returns here on close */
  triggerRef?: React.RefObject<HTMLElement | null>;
  children: ReactNode;
  isLoading?: boolean;
}

/** All focusable element selectors */
const FOCUSABLE_SELECTORS = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

export function ContentModal({
  isOpen,
  onClose,
  title,
  triggerRef,
  children,
  isLoading = false,
}: ContentModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Return focus to trigger element on close
  const handleClose = useCallback(() => {
    onClose();
    // Defer so the modal is unmounted before we try to focus
    requestAnimationFrame(() => {
      triggerRef?.current?.focus();
    });
  }, [onClose, triggerRef]);

  // Focus the close button when modal opens
  useEffect(() => {
    if (isOpen) {
      // Small delay to ensure the modal is rendered
      const timer = setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Focus trap: keep Tab/Shift+Tab inside the modal
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Escape') {
        handleClose();
        return;
      }

      if (e.key !== 'Tab') return;

      const dialog = dialogRef.current;
      if (!dialog) return;

      const focusable = Array.from(
        dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS)
      ).filter((el) => !el.closest('[aria-hidden="true"]'));

      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        // Shift+Tab: if focus is on first element, wrap to last
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        // Tab: if focus is on last element, wrap to first
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    },
    [handleClose]
  );

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        aria-hidden="true"
        onClick={handleClose}
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="content-modal-title"
        onKeyDown={handleKeyDown}
        className={cn(
          'fixed left-1/2 top-1/2 z-50 w-full max-w-2xl -translate-x-1/2 -translate-y-1/2',
          'flex max-h-[90vh] flex-col rounded-xl border border-border bg-background shadow-2xl',
          'focus:outline-none'
        )}
        tabIndex={-1}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-border px-6 py-4">
          <h2
            id="content-modal-title"
            className="text-base font-semibold text-foreground"
          >
            {title}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={handleClose}
            aria-label="Fechar modal"
            className={cn(
              'rounded-md p-1.5 text-muted-foreground transition-colors',
              'hover:bg-muted hover:text-foreground',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1'
            )}
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {isLoading && (
            <div
              className="flex items-center justify-center py-8"
              aria-live="polite"
              aria-label="Carregando conteúdo"
            >
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden="true" />
              <span className="ml-2 text-sm text-muted-foreground">Iniciando geração…</span>
            </div>
          )}
          {!isLoading && children}
        </div>
      </div>
    </>
  );
}
