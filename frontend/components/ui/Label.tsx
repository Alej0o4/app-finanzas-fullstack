import type { LabelHTMLAttributes, ReactNode } from 'react';

interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {
  children: ReactNode;
}

export default function Label({ children, className = '', ...rest }: LabelProps) {
  return (
    <label className={`text-text-soft text-sm font-medium ${className}`} {...rest}>
      {children}
    </label>
  );
}
