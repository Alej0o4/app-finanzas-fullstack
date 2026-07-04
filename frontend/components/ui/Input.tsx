"use client";

import { type InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = "", ...rest }, ref) => {
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label className="text-sm font-medium text-text-soft">{label}</label>
        )}
        <input
          ref={ref}
          className={`w-full rounded-xl border bg-surface px-4 py-2.5 text-sm text-text placeholder-text-muted/60 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary/50 ${
            error
              ? "border-danger/50 focus:ring-danger/50"
              : "border-border focus:border-primary/50"
          } ${className}`}
          {...rest}
        />
        {error && <span className="text-xs text-danger">{error}</span>}
      </div>
    );
  }
);

Input.displayName = "Input";

export default Input;
