interface StatusPillProps {
  label: string;
  tone?: "green" | "cyan" | "amber" | "slate" | "red";
  dot?: boolean;
}

export function StatusPill({ label, tone = "green", dot = false }: StatusPillProps) {
  const tones = {
    green: "border-green-400/30 bg-green-400/10 text-green-200",
    cyan: "border-teal-300/30 bg-teal-300/10 text-teal-100",
    amber: "border-amber-400/30 bg-amber-400/10 text-amber-200",
    slate: "border-slate-500/30 bg-slate-500/10 text-slate-300",
    red: "border-red-400/30 bg-red-400/10 text-red-200"
  };
  const dotTones = {
    green: "bg-green-300",
    cyan: "bg-teal-200",
    amber: "bg-amber-300",
    slate: "bg-slate-400",
    red: "bg-red-300"
  };

  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1 text-xs font-medium ${tones[tone]}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dotTones[tone]}`} />}
      {label}
    </span>
  );
}
