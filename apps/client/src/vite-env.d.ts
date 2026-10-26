/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENTRA_TENANT_ID: string;
  readonly VITE_ENTRA_CLIENT_ID: string;
  readonly VITE_SERVICE_A_SCOPE: string;
  readonly VITE_SERVICE_A_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
