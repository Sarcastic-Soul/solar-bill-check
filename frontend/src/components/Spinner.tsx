export default function Spinner({ label }: { label?: string }) {
  return (
    <div role="status" className="wrap flex min-h-[40vh] flex-col items-center justify-center gap-4">
      <span aria-hidden className="size-10 animate-spin rounded-full border-[3px] border-ink border-t-sun" />
      {label ? <p className="text-ink-2">{label}</p> : <span className="sr-only">Loading</span>}
    </div>
  );
}
