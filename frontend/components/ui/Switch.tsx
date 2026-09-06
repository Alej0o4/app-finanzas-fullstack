'use client';

import { type InputHTMLAttributes, forwardRef, useId } from 'react';

interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'size'> {
  label?: string;
  description?: string;
}

const Switch = forwardRef<HTMLInputElement, SwitchProps>(
  ({ label, description, id, className = '', disabled, ...rest }, ref) => {
    const generatedId = useId();
    const switchId = id ?? generatedId;

    return (
      <label
        htmlFor={switchId}
        className={`flex cursor-pointer items-center gap-3 ${disabled ? 'cursor-not-allowed opacity-50' : ''} ${className}`}
      >
        <span className="relative inline-flex shrink-0">
          <input
            ref={ref}
            id={switchId}
            type="checkbox"
            role="switch"
            disabled={disabled}
            className="peer sr-only"
            {...rest}
          />
          <span className="bg-border peer-checked:bg-primary peer-focus-visible:ring-primary/50 after:bg-text h-6 w-11 rounded-full transition-colors duration-200 peer-focus-visible:ring-2 peer-focus-visible:outline-none after:pointer-events-none after:absolute after:top-[2px] after:left-[2px] after:h-5 after:w-5 after:rounded-full after:shadow-sm after:transition-transform after:duration-200 after:content-[''] peer-checked:after:translate-x-5" />
        </span>
        {(label || description) && (
          <span className="flex flex-col gap-0.5">
            {label && <span className="text-text text-sm font-medium">{label}</span>}
            {description && <span className="text-text-muted text-xs">{description}</span>}
          </span>
        )}
      </label>
    );
  }
);

Switch.displayName = 'Switch';

export default Switch;
