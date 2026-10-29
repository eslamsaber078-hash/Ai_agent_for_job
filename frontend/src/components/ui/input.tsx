import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, title, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      // A single-line field hides the tail of a long value; hover reveals what doesn't fit.
      title={title ?? (typeof props.value === "string" && props.value.length > 24 ? props.value : undefined)}
      className={cn(
        "flex h-10 w-full rounded-xl border border-transparent bg-muted/70 px-3.5 py-2 text-sm shadow-inset transition-[background-color,border-color,box-shadow] duration-200 ease-smooth placeholder:text-muted-foreground/75 hover:bg-muted focus-visible:border-ring/45 focus-visible:bg-card focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/10 disabled:cursor-not-allowed disabled:opacity-50 file:border-0 file:bg-transparent file:text-sm file:font-medium dark:shadow-none",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
