import { broadcastResponseToMainFrame } from "@azure/msal-browser/redirect-bridge";

// msal-browser 5.x requires the redirect URI page to hand the auth response
// back to the window that opened the popup. This page must stay minimal: it
// must not load the SPA or initialize MSAL again.
broadcastResponseToMainFrame().catch((error: unknown) => {
  console.error("[auth] Failed to complete the authentication redirect", error);
});
