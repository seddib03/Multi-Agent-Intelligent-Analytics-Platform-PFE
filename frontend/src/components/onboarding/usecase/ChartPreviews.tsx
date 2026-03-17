/* eslint-disable react-refresh/only-export-components */
import type { ChartStyle } from "@/types/app";

function BarPreview() {
  return (
    <svg width="80" height="50" viewBox="0 0 80 50">
      <rect x="5" y="20" width="12" height="30" fill="#004AAC" rx="2" />
      <rect x="22" y="10" width="12" height="40" fill="#FF7E51" rx="2" />
      <rect x="39" y="25" width="12" height="25" fill="#FFAE41" rx="2" />
      <rect x="56" y="15" width="12" height="35" fill="#4995FF" rx="2" />
    </svg>
  );
}

function LinePreview() {
  return (
    <svg width="80" height="50" viewBox="0 0 80 50">
      <path d="M5 40 Q20 10 40 25 T75 15" stroke="#004AAC" strokeWidth="2.5" fill="none" />
    </svg>
  );
}

function PiePreview() {
  return (
    <svg width="50" height="50" viewBox="0 0 50 50">
      <circle cx="25" cy="25" r="20" fill="none" stroke="#004AAC" strokeWidth="8" strokeDasharray="50 76" strokeDashoffset="0" />
      <circle cx="25" cy="25" r="20" fill="none" stroke="#FF7E51" strokeWidth="8" strokeDasharray="30 96" strokeDashoffset="-50" />
      <circle cx="25" cy="25" r="20" fill="none" stroke="#FFAE41" strokeWidth="8" strokeDasharray="46 80" strokeDashoffset="-80" />
    </svg>
  );
}

function AreaPreview() {
  return (
    <svg width="80" height="50" viewBox="0 0 80 50">
      <path d="M0 50 L10 30 L30 35 L50 15 L70 20 L80 10 L80 50 Z" fill="#A1E6FF" opacity="0.5" />
      <path d="M0 50 L10 30 L30 35 L50 15 L70 20 L80 10" stroke="#A1E6FF" strokeWidth="2" fill="none" />
    </svg>
  );
}

function HeatPreview() {
  const colors = ["#FFC982", "#FFAE41", "#FF7E51", "#FFC982", "#FF7E51", "#D14600", "#FFAE41", "#FFC982", "#FF7E51"];
  return (
    <svg width="54" height="54" viewBox="0 0 54 54">
      {colors.map((c, i) => (
        <rect key={i} x={(i % 3) * 18} y={Math.floor(i / 3) * 18} width="16" height="16" rx="2" fill={c} />
      ))}
    </svg>
  );
}

export const ChartPreviews: Record<ChartStyle, React.FC> = {
  bar: BarPreview,
  line: LinePreview,
  pie: PiePreview,
  area: AreaPreview,
  heatmap: HeatPreview,
};
