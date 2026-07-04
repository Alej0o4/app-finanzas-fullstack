import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: ReactNode;
  message: string;
  description?: string;
}

export default function EmptyState({
  icon,
  message,
  description,
}: EmptyStateProps) {
  return (
    <div className="p-12 text-center flex flex-col items-center text-text-muted">
      <div className="mb-3">{icon}</div>
      <p className="text-sm font-medium">{message}</p>
      {description && (
        <p className="mt-1 text-xs text-text-muted/70">{description}</p>
      )}
    </div>
  );
}
