'use client';

import { type InputHTMLAttributes, forwardRef, useId } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, id, className = '', ...rest }, ref) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;
    return (
      <div className="min-w-0 flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-text-soft text-sm font-medium">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`bg-surface text-text placeholder-text-muted/60 focus-visible:ring-primary/50 min-w-0 w-full rounded-xl border px-4 py-2.5 text-sm transition-colors duration-200 focus-visible:ring-2 focus-visible:outline-none ${
            error
              ? 'border-danger/50 focus-visible:ring-danger/50'
              : 'border-border focus:border-primary/50'
          } ${className}`}
          {...rest}
        />
        {error && <span className="text-danger text-xs">{error}</span>}
      </div>
    );
  }
);

Input.displayName = 'Input';

export default Input;
