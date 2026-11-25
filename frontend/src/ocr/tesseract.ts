import { createWorker, OEM, type Worker } from "tesseract.js";

const OCR_FILES = `${window.location.origin}/ocr`;

let workerPromise: Promise<Worker> | null = null;

export async function recognizeText(image: Blob): Promise<string> {
  if (workerPromise === null) {
    // tesseract.js 7's createWorker never settles if the language data fails to load or
    // initialize, but it does call errorHandler. Rejecting from there turns the hang into a
    // failure that the .catch below can forget.
    workerPromise = new Promise<Worker>((resolve, reject) => {
      createWorker("eng", OEM.LSTM_ONLY, {
        workerPath: `${OCR_FILES}/worker.min.js`,
        corePath: `${OCR_FILES}/core`,
        langPath: `${OCR_FILES}/lang`,
        errorHandler: reject,
      }).then(resolve, reject);
    }).catch((err) => {
      workerPromise = null;
      throw err;
    });
  }
  const worker = await workerPromise;
  const { data } = await worker.recognize(image);
  return data.text;
}
