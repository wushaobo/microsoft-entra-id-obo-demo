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

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
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
