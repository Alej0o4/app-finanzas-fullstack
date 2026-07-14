'use client';

import * as Icons from 'lucide-react';

interface CategoryIconProps {
  icon?: string | null;
  size?: number;
  className?: string;
  fallback?: React.ReactNode;
}

export default function CategoryIcon({ icon, size = 18, className, fallback }: CategoryIconProps) {
  if (!icon) return fallback ?? null;
  const LucideIcon = (Icons as Record<string, unknown>)[icon] as
    React.ComponentType<{ size?: number; className?: string }> | undefined;
  if (!LucideIcon) return fallback ?? null;
  return <LucideIcon size={size} className={className} />;
}
