import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";

// jsdom lacks these browser APIs. The theme reads matchMedia; menus and popovers may use the rest.
// matchMedia reports a light-mode device; a test that needs dark mocks it with vi.spyOn.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  configurable: true,
  value: (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent: () => false,
    }) as MediaQueryList,
});

globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.releasePointerCapture ??= () => {};
Element.prototype.scrollIntoView ??= () => {};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
  localStorage.clear();
  document.documentElement.classList.remove("dark");
});
