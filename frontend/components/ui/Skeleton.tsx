interface SkeletonProps {
  className?: string;
}

export default function Skeleton({ className = "" }: SkeletonProps) {
  return (
    <div
      className={`bg-surface-elevated animate-pulse rounded-xl ${className}`}
    />
  );
}
