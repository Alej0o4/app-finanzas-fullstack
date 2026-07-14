import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon: ReactNode;
  message: string;
  description?: string;
}

export default function EmptyState({ icon, message, description }: EmptyStateProps) {
  return (
    <div className="text-text-muted flex flex-col items-center p-12 text-center">
      <div className="mb-3">{icon}</div>
      <p className="text-sm font-medium">{message}</p>
      {description && <p className="text-text-muted/70 mt-1 text-xs">{description}</p>}
    </div>
  );
}
