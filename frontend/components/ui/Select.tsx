"use client";

import { type SelectHTMLAttributes, forwardRef } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, children, className = "", ...rest }, ref) => {
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label className="text-sm font-medium text-text-soft">{label}</label>
        )}
        <select
          ref={ref}
          className={`w-full rounded-xl border bg-surface px-4 py-2.5 text-sm text-text transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary/50 ${
            error
              ? "border-danger/50 focus:ring-danger/50"
              : "border-border focus:border-primary/50"
          } ${className}`}
          {...rest}
        >
          {children}
        </select>
        {error && <span className="text-xs text-danger">{error}</span>}
      </div>
    );
  }
);

Select.displayName = "Select";

export default Select;
