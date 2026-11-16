import { useEffect, useId, useRef, useState } from 'react';
import type { Replay } from './evidence';
import { percent } from './evidence';

export default function ForecastChart({ replay, index, horizon, onSeek }: { replay: Replay; index: number; horizon: number; onSeek: (i: number) => void }) {
  const gradient = useId();
  const [hover, setHover] = useState<number | null>(null);
  const wrapper = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  useEffect(() => {
    if (!wrapper.current) return;
    const observer = new ResizeObserver(entries => setWidth(Math.max(360, Math.round(entries[0].contentRect.width))));
    observer.observe(wrapper.current);
    return () => observer.disconnect();
  }, []);
  const height = 290, left = width < 500 ? 37 : 46, right = 24, top = 28, bottom = 34;
  const points = replay.points;
  if (!points.length) return <p className="demo-empty">No pre-outcome forecasts in this campaign window.</p>;
  const hi = replay.horizons.indexOf(horizon);
  const span = points[0].minutes_before;
  const x = (i: number) => left + (span - points[i].minutes_before) / span * (width - left - right);
  const y = (v: number) => top + (1 - v) * (height - top - bottom);
  const path = (end: number) => points.slice(0, end + 1).map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(2)},${y(p.risk[hi]).toFixed(2)}`).join(' ');
  const selected = hover ?? index;
  const focusX = x(selected), focusY = y(points[selected].risk[hi]);
  const fromPointer = (event: React.PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const minute = span * (1 - ((event.clientX - rect.left) / rect.width * width - left) / (width - left - right));
    return points.reduce((best, point, i) => Math.abs(point.minutes_before - minute) < Math.abs(points[best].minutes_before - minute) ? i : best, 0);
  };
  return <div className="demo-chart-wrap" ref={wrapper}>
    <svg className="demo-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Archived ${horizon}-minute risk forecast. Use the timeline slider below to seek.`}
      onPointerMove={event => setHover(fromPointer(event))} onPointerLeave={() => setHover(null)} onPointerDown={event => onSeek(fromPointer(event))}>
      <defs><linearGradient id={gradient} x1="0" x2="0" y1="0" y2="1"><stop stopColor="#10a58c" stopOpacity=".24"/><stop offset="1" stopColor="#10a58c" stopOpacity=".015"/></linearGradient></defs>
      {[0, .25, .5, .75, 1].map(v => <g key={v}><line x1={left} x2={width-right} y1={y(v)} y2={y(v)} stroke="#e8eceb" strokeDasharray="3 5"/><text x={left-12} y={y(v)+4} textAnchor="end">{v*100}%</text></g>)}
      {(width < 500 ? [180, 120, 60, 0] : [180, 150, 120, 90, 60, 30, 0]).filter(v => v <= span + 1).map(v => <g key={v}><text x={left+(1-v/span)*(width-left-right)} y={height-9} textAnchor="middle">{v === 0 ? 'Outcome' : `−${v}m`}</text></g>)}
      <rect x={left+(1-horizon/span)*(width-left-right)} y={top} width={horizon/span*(width-left-right)} height={height-top-bottom} fill="#10a58c" opacity=".035"/>
      <path d={path(points.length-1)} stroke="#9ccfc3" strokeWidth="1.8" fill="none" strokeDasharray="3 4"/>
      <path d={`${path(index)} L${x(index)},${y(0)} L${left},${y(0)} Z`} fill={`url(#${gradient})`}/>
      {replay.threshold <= 1 && <><line x1={left} x2={width-right} y1={y(replay.threshold)} y2={y(replay.threshold)} stroke="#d6a345" strokeWidth="1.3" strokeDasharray="6 5"/><text x={left+7} y={y(replay.threshold)-8} className="demo-threshold-label">Warning threshold · {percent(replay.threshold)}</text></>}
      <path d={path(index)} stroke="#13967e" strokeWidth="2.8" strokeLinejoin="round" strokeLinecap="round" fill="none"/>
      {points.map((point, i) => point.episode_start && i <= index ? <circle key={i} cx={x(i)} cy={y(point.risk[hi])} r="4" fill="#d7a23e" stroke="white" strokeWidth="2"><title>New warning · {point.minutes_before.toFixed(1)} minutes before outcome</title></circle> : null)}
      <line x1={width-right} x2={width-right} y1={top} y2={height-bottom} stroke="#d59494" strokeDasharray="3 4"/>
      <line x1={focusX} x2={focusX} y1={top} y2={height-bottom} stroke="#6e9990" strokeDasharray="3 4"/>
      <circle cx={focusX} cy={focusY} r="8" fill="#13967e" fillOpacity=".15"/><circle cx={focusX} cy={focusY} r="4" fill="#13967e" stroke="white" strokeWidth="2"/>
      {hover !== null && <g transform={`translate(${Math.max(left, Math.min(focusX-65, width-right-142))},${Math.max(2, focusY-48)})`}><rect width="142" height="34" rx="6" fill="#153d36"/><text x="71" y="21" textAnchor="middle" style={{ fill: 'white', fontSize: 11 }}>{percent(points[selected].risk[hi])} · −{points[selected].minutes_before.toFixed(1)} min</text></g>}
    </svg>
    <div className="demo-chart-caption"><span>← Earlier in campaign</span><span>Successful root access · retrospective marker</span></div>
  </div>;
}
