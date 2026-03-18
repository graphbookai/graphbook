export const RUN_COLOR_PALETTE = [
  '#60a5fa', // blue-400
  '#fb923c', // orange-400
  '#34d399', // emerald-400
  '#a78bfa', // violet-400
  '#fb7185', // rose-400
  '#22d3ee', // cyan-400
  '#fbbf24', // amber-400
  '#a3e635', // lime-400
  '#f472b6', // pink-400
  '#2dd4bf', // teal-400
  '#818cf8', // indigo-400
  '#f87171', // red-400
]

export function assignColor(index: number): string {
  return RUN_COLOR_PALETTE[index % RUN_COLOR_PALETTE.length]
}
