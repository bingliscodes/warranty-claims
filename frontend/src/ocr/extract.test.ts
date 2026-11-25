import { extractMileage, extractVin } from "./extract";

test.each([
  ["VIN 1M8GDM9AXKP042788", "1M8GDM9AXKP042788"],
  ["vin: 1m8gdm9axkpo42788", "1M8GDM9AXKP042788"],
  ["1M8 GDM9AX KP042788", "1M8GDM9AXKP042788"],
  ["VIN 1M8 GDM9AX KP042788", "1M8GDM9AXKP042788"],
  ["VEHICLEIDNO1M8GDM9AXKP042788", "1M8GDM9AXKP042788"],
  ["MFG 05/24 GVWR 4500\nVIN 1M8GDM9AXKP042788\nMADE IN USA", "1M8GDM9AXKP042788"],
  ["WVWZZZ1JZXW000001", "WVWZZZ1JZXW000001"],
  // Two candidates: the one that passes the check digit wins, even when it comes second.
  ["WVWZZZ1JZXW000001\nVIN 1M8GDM9AXKP042788", "1M8GDM9AXKP042788"],
  ["no vin here 12345", null],
  ["1M8GDM9AXKP04278", null],
])("extractVin(%j)", (text, expected) => expect(extractVin(text)).toBe(expected));

test.each([
  ["ODO 1599 mi", 1599],
  ["TRIP A 245.3  ODO 45,210", 45210],
  ["12:45 72F\n45210", 45210],
  ["ODO 1,234,567", 1234567],
  ["CALL 6085551234", null],
  ["no digits", null],
])("extractMileage(%j)", (text, expected) => expect(extractMileage(text)).toBe(expected));
