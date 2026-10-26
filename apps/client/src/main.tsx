import { EventType, type AuthenticationResult } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { logoutPendingKey, msalInstance } from "./authConfig";
import "./styles.css";

async function bootstrap() {
  await msalInstance.initialize();

  const redirectResult = await msalInstance.handleRedirectPromise();

  // Returned from logoutRedirect: clear everything left in this origin.
  if (window.sessionStorage.getItem(logoutPendingKey) === "1") {
    msalInstance.setActiveAccount(null);
    window.localStorage.clear();
    window.sessionStorage.clear();
  }

  if (redirectResult?.account) {
    msalInstance.setActiveAccount(redirectResult.account);
  } else {
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) {
      msalInstance.setActiveAccount(accounts[0]);
    }
  }

  msalInstance.addEventCallback((event) => {
    if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
      const payload = event.payload as AuthenticationResult;
      if (payload.account) {
        msalInstance.setActiveAccount(payload.account);
      }
    }
  });

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <MsalProvider instance={msalInstance}>
        <App />
      </MsalProvider>
    </StrictMode>,
  );
}

void bootstrap();
