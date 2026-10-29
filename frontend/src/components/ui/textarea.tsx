import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-[80px] w-full rounded-xl border border-transparent bg-muted/70 px-3.5 py-2.5 text-sm leading-relaxed shadow-inset transition-[background-color,border-color,box-shadow] duration-200 ease-smooth placeholder:text-muted-foreground/75 hover:bg-muted focus-visible:border-ring/45 focus-visible:bg-card focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/10 disabled:cursor-not-allowed disabled:opacity-50 dark:shadow-none",
        className
      )}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";
