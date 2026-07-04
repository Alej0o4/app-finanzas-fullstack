import type { LabelHTMLAttributes, ReactNode } from "react";

interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {
  children: ReactNode;
}

export default function Label({ children, className = "", ...rest }: LabelProps) {
  return (
    <label
      className={`text-sm font-medium text-text-soft ${className}`}
      {...rest}
    >
      {children}
    </label>
  );
}
