/**
 * Trims, uppercases and removes spaces. The backend's VIN lookup is strict (design §8), so the
 * phone sends a VIN through this first.
 */
export function normalizeVin(raw: string): string {
  return raw.replace(/\s+/g, "").toUpperCase();
}

/** The VIN rule, the same as the backend's: 17 uppercase letters or digits, never I, O or Q. */
export function isValidVin(vin: string): boolean {
  return /^[A-HJ-NPR-Z0-9]{17}$/.test(vin);
}

// The check digit's value for each letter. A digit counts as its own value.
const LETTER_VALUES: Record<string, number> = {
  A: 1,
  B: 2,
  C: 3,
  D: 4,
  E: 5,
  F: 6,
  G: 7,
  H: 8,
  J: 1,
  K: 2,
  L: 3,
  M: 4,
  N: 5,
  P: 7,
  R: 9,
  S: 2,
  T: 3,
  U: 4,
  V: 5,
  W: 6,
  X: 7,
  Y: 8,
  Z: 9,
};

// One weight per position. Position 9 (index 8) holds the check digit itself, so its weight is 0.
const WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2];

/**
 * Whether position 9 holds the right North American check digit. Returns false, never throws,
 * for anything that isn't VIN-shaped (owner's call, 2026-11-25).
 */
export function vinCheckDigitValid(vin: string): boolean {
  if (!isValidVin(vin)) return false;
  let sum = 0;
  for (let i = 0; i < vin.length; i++) {
    const char = vin[i];
    let value;
    if (!Number.isNaN(Number(char))) value = Number(char);
    else value = LETTER_VALUES[char];

    sum += WEIGHTS[i] * value;
  }
  const remainder = sum % 11;
  const expected = remainder === 10 ? "X" : String(remainder);
  return expected === vin[8];
}
