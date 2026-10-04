'use client';

import { AlertCircle } from 'lucide-react';
import EmptyState from '@/components/ui/EmptyState';
import Button from '@/components/ui/Button';

export default function QueryErrorState({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <EmptyState
      icon={<AlertCircle size={48} className="opacity-20" />}
      message={message}
      className={className}
      action={
        onRetry ? (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Reintentar
          </Button>
        ) : null
      }
    />
  );
}
