export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background min-h-screen">
      <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6">{children}</div>
    </div>
  );
}
