interface YearRange {
  min: number;
  max: number;
}

const DEFAULT_STEP_YEARS: YearRange = { min: 5, max: 5 };

// Mirrors backend defaults in backend/config/runtime.yaml:
// depth 1 -> 5 years, depth 2 -> 2-3 years, depth >=3 -> fallback 5 years.
const STEP_YEARS_BY_DEPTH: Record<number, YearRange> = {
  1: { min: 5, max: 5 },
  2: { min: 2, max: 3 },
};

function stepRange(depth: number): YearRange {
  return STEP_YEARS_BY_DEPTH[depth] ?? DEFAULT_STEP_YEARS;
}

function cumulativeRange(depth: number): YearRange {
  if (depth <= 0) {
    return { min: 0, max: 0 };
  }

  let min = 0;
  let max = 0;

  for (let d = 1; d <= depth; d += 1) {
    const step = stepRange(d);
    min += step.min;
    max += step.max;
  }

  return { min, max };
}

function formatYears(range: YearRange): string {
  if (range.min === 0 && range.max === 0) {
    return "Present";
  }

  if (range.min === range.max) {
    return `~${range.min} years ahead`;
  }

  return `~${range.min}-${range.max} years ahead`;
}

export function getTimeHorizonLabel(depth: number): string {
  return formatYears(cumulativeRange(depth));
}

