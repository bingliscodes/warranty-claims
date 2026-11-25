import { isValidVin, normalizeVin, vinCheckDigitValid } from "./vin";

test("VIN format", () => {
  expect(isValidVin("1M8GDM9AXKP042788")).toBe(true);
  expect(isValidVin("1M8GDM9AXKP04278")).toBe(false);
  expect(isValidVin("1M8GDM9AXKPO42788")).toBe(false);
  expect(normalizeVin(" 1m8 gdm9axkp042788 ")).toBe("1M8GDM9AXKP042788");
});

test("check digit", () => {
  expect(vinCheckDigitValid("1M8GDM9AXKP042788")).toBe(true);
  expect(vinCheckDigitValid("11111111111111111")).toBe(true);
  expect(vinCheckDigitValid("WVWZZZ1JZXW000001")).toBe(false);
  // Half-typed: its first 9 characters happen to sum to the "X" at position 9.
  expect(vinCheckDigitValid("1M8GDM9AX")).toBe(false);
});
