'use client';

import { type SelectHTMLAttributes, forwardRef, useId } from 'react';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, children, id, className = '', ...rest }, ref) => {
    const generatedId = useId();
    const selectId = id ?? generatedId;
    return (
      <div className="min-w-0 flex flex-col gap-1.5">
        {label && (
          <label htmlFor={selectId} className="text-text-soft text-sm font-medium">
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={`bg-surface text-text focus-visible:ring-primary/50 min-w-0 w-full rounded-xl border px-4 py-2.5 text-sm transition-colors duration-200 focus-visible:ring-2 focus-visible:outline-none ${
            error
              ? 'border-danger/50 focus-visible:ring-danger/50'
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
