import { initials } from "@/lib/format";

const HUES = [221, 262, 174, 28, 340, 199, 142, 12];
export function Avatar({ name, size = 36 }: { name: string; size?: number }) {
  const h = HUES[[...name].reduce((a, c) => a + c.charCodeAt(0), 0) % HUES.length];
  return (
    <span className="grid shrink-0 place-items-center rounded-full font-semibold" aria-hidden
      style={{ width: size, height: size, fontSize: size * 0.38, background: `hsl(${h} 70% 92%)`, color: `hsl(${h} 55% 32%)` }}>{initials(name)}</span>
  );
}
