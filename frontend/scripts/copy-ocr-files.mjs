// Copies Tesseract.js's worker, OCR engine and English language data into public/ocr/, so the
// app serves them itself instead of the jsDelivr CDN (design §8). Vite serves public/ in
// development and copies it into dist/ on build. Runs before `npm run dev` and `npm run build`.
import { copyFileSync, mkdirSync } from "node:fs";

// node_modules path → path under public/ocr/.
const FILES = {
  "tesseract.js/dist/worker.min.js": "worker.min.js",
  // Tesseract.js uses its LSTM engine by default and picks the build the device supports.
  "tesseract.js-core/tesseract-core-lstm.wasm.js": "core/tesseract-core-lstm.wasm.js",
  "tesseract.js-core/tesseract-core-simd-lstm.wasm.js": "core/tesseract-core-simd-lstm.wasm.js",
  "tesseract.js-core/tesseract-core-relaxedsimd-lstm.wasm.js":
    "core/tesseract-core-relaxedsimd-lstm.wasm.js",
  "@tesseract.js-data/eng/4.0.0_best_int/eng.traineddata.gz": "lang/eng.traineddata.gz",
};

const nodeModules = new URL("../node_modules/", import.meta.url);
const ocrDir = new URL("../public/ocr/", import.meta.url);

for (const [from, to] of Object.entries(FILES)) {
  const target = new URL(to, ocrDir);
  mkdirSync(new URL(".", target), { recursive: true });
  copyFileSync(new URL(from, nodeModules), target);
}
