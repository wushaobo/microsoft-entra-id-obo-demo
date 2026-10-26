import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// Serve the minimal redirect bridge page at /redirect while keeping
// redirect.html as the internal HTML entry. Without this rewrite, Vite's SPA
// fallback would return index.html and break the MSAL redirect bridge.
function redirectAlias(): Plugin {
  return {
    name: "redirect-alias",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((req, _res, next) => {
        // Connect's request type is incomplete without Node's type definitions;
        // this middleware only needs the URL.
        const request = req as { url?: string };
        const url = request.url;
        if (url && (url === "/redirect" || url.startsWith("/redirect?"))) {
          request.url = url.replace("/redirect", "/redirect.html");
        }
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [redirectAlias(), react()],
  server: {
    port: 5173,
    strictPort: true,
  },
});
