export function getGridDimensions(n: number): { cols: number; rows: number } {
  if (n <= 0) return { cols: 1, rows: 1 }
  const cols = Math.ceil(Math.sqrt(n))
  const rows = Math.ceil(n / cols)
  return { cols, rows }
}
