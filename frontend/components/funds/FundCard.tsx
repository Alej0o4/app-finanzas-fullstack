import Link from 'next/link';
import { Archive } from 'lucide-react';
import FundProgress from '@/components/funds/FundProgress';
import { KIND_LABELS, PaceChip } from '@/components/funds/fundPresentation';
import type { Fund } from '@/types/api';

export default function FundCard({ fund }: { fund: Fund }) {
  return (
    <div className="border-border bg-surface relative rounded-2xl border p-4 sm:p-5">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-text truncate font-semibold">
            <Link
              href={`/funds/${fund.id}`}
              className="after:absolute after:inset-0 after:rounded-2xl focus-visible:outline-none"
            >
              {fund.name}
            </Link>
          </h2>
          <p className="text-text-muted text-xs">{KIND_LABELS[fund.kind]}</p>
        </div>
        {fund.status === 'archived' ? (
          <span className="bg-surface-elevated text-text-muted inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs">
            <Archive size={12} aria-hidden="true" />
            Archivado
          </span>
        ) : (
          <PaceChip pace={fund.pace} />
        )}
      </div>
      <FundProgress fund={fund} />
    </div>
  );
}
