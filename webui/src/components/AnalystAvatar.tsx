/** Circular initials avatar — Figma DocumentsScreen analyst column. */

const palette = ["#003B5C", "#1D4ED8", "#7C3AED", "#0D9488", "#B45309"];

function hash(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h << 5) - h + s.charCodeAt(i);
  return Math.abs(h);
}

export function AnalystAvatar({ name }: { name: string }) {
  const parts = name.trim().split(/\s+/);
  const initials =
    parts.length >= 2
      ? `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
      : name.slice(0, 2).toUpperCase();
  const bg = palette[hash(name) % palette.length];

  return (
    <div className="flex items-center gap-2.5">
      <div
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-white"
        style={{ backgroundColor: bg }}
      >
        {initials}
      </div>
      <span className="text-sm text-brand-ink">{name}</span>
    </div>
  );
}
