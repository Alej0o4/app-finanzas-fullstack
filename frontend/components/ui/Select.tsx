'use client';

import { type SelectHTMLAttributes, forwardRef } from 'react';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, children, className = '', ...rest }, ref) => {
    return (
      <div className="min-w-0 flex flex-col gap-1.5">
        {label && <label className="text-text-soft text-sm font-medium">{label}</label>}
        <select
          ref={ref}
          className={`bg-surface text-text focus:ring-primary/50 min-w-0 w-full rounded-xl border px-4 py-2.5 text-sm transition-colors duration-200 focus:ring-2 focus:outline-none ${
            error
              ? 'border-danger/50 focus:ring-danger/50'
              : 'border-border focus:border-primary/50'
          } ${className}`}
          {...rest}
        >
          {children}
        </select>
        {error && <span className="text-danger text-xs">{error}</span>}
      </div>
    );
  }
);

Select.displayName = 'Select';

export default Select;
