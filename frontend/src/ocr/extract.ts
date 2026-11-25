import { isValidVin, vinCheckDigitValid } from "../lib/vin";

// Splits an uppercased line into tokens on any run of characters that aren't A–Z or 0–9.
const TOKEN_SEPARATOR = /[^A-Z0-9]+/;

// A number with thousands commas ("45,210") or a plain run of digits ("1599").
const NUMBER = /\d{1,3}(?:,\d{3})+|\d+/g;

/** The VIN in OCR text, or null. Tries the strongest evidence first (plan Task 12, Step 3). */
export function extractVin(text: string): string | null {
  text = text
    .toUpperCase()
    .replaceAll("I", "1")
    .replaceAll("O", "0")
    .replaceAll("Q", "0");

  const lines = text.split("\n").map((line) => line.split(TOKEN_SEPARATOR));
  for (const tokens of lines) {
    for (const token of tokens) {
      if (vinCheckDigitValid(token)) return token;
    }
  }

  for (const tokens of lines) {
    for (let i = 0; i < tokens.length; i++) {
      let join = "";
      for (let j = i; j < tokens.length; j++) {
        join += tokens[j];
        if (join.length === 17 && vinCheckDigitValid(join)) return join;
        if (join.length >= 17) break;
      }
    }
  }

  for (const tokens of lines) {
    for (const token of tokens) {
      if (isValidVin(token)) return token;
    }
  }

  for (const tokens of lines) {
    for (const token of tokens) {
      for (let i = 0; i <= token.length - 17; i++) {
        const candidate = token.slice(i, i + 17);
        if (vinCheckDigitValid(candidate)) return candidate;
      }
    }
  }
  return null;
}

/** The mileage in OCR text (the largest number of at most 7 digits), or null. */
export function extractMileage(text: string): number | null {
  const numbers = text.match(NUMBER) ?? [];

  const mileages = numbers
    .map((num) => Number(num.replaceAll(",", "")))
    .filter((num) => num < 10_000_000);

  if (mileages.length === 0) return null;

  return Math.max(...mileages);
}
