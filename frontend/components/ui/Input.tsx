'use client';

import { type InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', ...rest }, ref) => {
    return (
      <div className="flex flex-col gap-1.5">
        {label && <label className="text-text-soft text-sm font-medium">{label}</label>}
        <input
          ref={ref}
          className={`bg-surface text-text placeholder-text-muted/60 focus:ring-primary/50 w-full rounded-xl border px-4 py-2.5 text-sm transition-colors duration-200 focus:ring-2 focus:outline-none ${
            error
              ? 'border-danger/50 focus:ring-danger/50'
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
