'use client';
interface Props { bars?: number; size?: 'sm' | 'md' | 'lg'; }
export function AIWaveform({ bars = 5, size = 'md' }: Props) {
  const heights = [10, 18, 24, 18, 10];
  const widths = { sm: 3, md: 3.5, lg: 4 };
  return (
    <div className="flex items-end gap-[3px]" style={{ height: size === 'sm' ? 20 : size === 'lg' ? 30 : 24 }}>
      {Array.from({ length: bars }).map((_, i) => (
        <div key={i} style={{
          width: widths[size],
          height: heights[i % heights.length],
          borderRadius: 2,
          background: 'var(--ai-grad)',
          animation: `wave-bar 1.4s ease-in-out ${i * 0.15}s infinite`,
          transformOrigin: 'bottom',
        }} />
      ))}
    </div>
  );
}
