import {
  LogLevel,
  PublicClientApplication,
  type Configuration,
} from "@azure/msal-browser";

const env = {
  VITE_ENTRA_TENANT_ID: import.meta.env.VITE_ENTRA_TENANT_ID,
  VITE_ENTRA_CLIENT_ID: import.meta.env.VITE_ENTRA_CLIENT_ID,
  VITE_SERVICE_A_SCOPE: import.meta.env.VITE_SERVICE_A_SCOPE,
  VITE_SERVICE_A_BASE_URL: import.meta.env.VITE_SERVICE_A_BASE_URL,
};

const missingVariables = Object.entries(env)
  .filter(([, value]) => !value?.trim())
  .map(([name]) => name);

if (missingVariables.length > 0) {
  throw new Error(
    `Missing required environment variables: ${missingVariables.join(", ")}. ` +
      "Copy env.example to .env and fill in the values.",
  );
}

const tenantId = env.VITE_ENTRA_TENANT_ID;
const clientId = env.VITE_ENTRA_CLIENT_ID;

export const serviceAScope = env.VITE_SERVICE_A_SCOPE;
export const serviceABaseUrl = env.VITE_SERVICE_A_BASE_URL.replace(/\/+$/, "");

// msal-browser 5.x needs a dedicated redirect page that runs the redirect
// bridge. Register this exact URI as a SPA redirect URI in Entra.
export const redirectUri = new URL(
  "/redirect.html",
  window.location.origin,
).href;

// Set before logoutRedirect so the reloaded app knows it is returning from
// logout and can clear all remaining browser state.
export const logoutPendingKey = "entra-obo-demo.logout-pending";

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri,
    postLogoutRedirectUri: redirectUri,
  },
  cache: {
    cacheLocation: "localStorage",
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Warning,
      piiLoggingEnabled: false,
    },
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);
