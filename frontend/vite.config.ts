// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

const apiOrigin = process.env["MUCLEGAL_API_ORIGIN"] ?? "http://127.0.0.1:8000";

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
  vite: {
    server: {
      proxy: {
        "/beweis-labor": { target: apiOrigin, changeOrigin: true },
        "/api": {
          target: apiOrigin,
          changeOrigin: true,
          headers: { origin: apiOrigin },
        },
        "/artifact": { target: apiOrigin, changeOrigin: true },
        "/static": { target: apiOrigin, changeOrigin: true },
      },
    },
  },
});
