import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { useState } from "react";

import { fetchFromServiceA } from "./api";
import { logoutPendingKey, redirectUri, serviceAScope } from "./authConfig";
import { useApiToken } from "./useApiToken";

type PanelState = {
  loading: boolean;
  output: string;
};

const emptyPanel: PanelState = { loading: false, output: "" };

function formatError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function formatResponse(body: string): string {
  try {
    return JSON.stringify(JSON.parse(body), null, 2);
  } catch {
    return body;
  }
}

export default function App() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const getToken = useApiToken();

  const [loginError, setLoginError] = useState("");
  const [serviceA, setServiceA] = useState<PanelState>(emptyPanel);
  const [serviceB, setServiceB] = useState<PanelState>(emptyPanel);

  const account = instance.getActiveAccount() ?? accounts[0];
  const displayName = account?.name?.trim();
  const statusText = !isAuthenticated
    ? "Not logged in"
    : account
      ? displayName && displayName !== account.username
        ? `Signed in as ${displayName} (${account.username})`
        : `Signed in as ${account.username}`
      : "Signed in";

  const handleLogin = async () => {
    setLoginError("");
    try {
      const result = await instance.loginPopup({ scopes: [serviceAScope] });
      instance.setActiveAccount(result.account);
    } catch (error) {
      setLoginError(formatError(error));
    }
  };

  const handleLogout = async () => {
    setLoginError("");
    // logoutRedirect leaves the page, so the flag survives in sessionStorage
    // and is consumed by main.tsx when the app loads again.
    window.sessionStorage.setItem(logoutPendingKey, "1");

    try {
      await instance.logoutRedirect({
        account: account ?? undefined,
        postLogoutRedirectUri: redirectUri,
      });
    } catch (error) {
      window.sessionStorage.removeItem(logoutPendingKey);
      setLoginError(formatError(error));
    }
  };

  const loadServiceA = async () => {
    setServiceA({ loading: true, output: "" });
    try {
      const accessToken = await getToken();
      const body = await fetchFromServiceA("/api/data", accessToken);
      setServiceA({ loading: false, output: formatResponse(body) });
    } catch (error) {
      setServiceA({ loading: false, output: formatError(error) });
    }
  };

  const loadServiceB = async () => {
    setServiceB({ loading: true, output: "" });
    try {
      const accessToken = await getToken();
      const body = await fetchFromServiceA(
        "/api/data-from-downstream",
        accessToken,
      );
      setServiceB({ loading: false, output: formatResponse(body) });
    } catch (error) {
      setServiceB({ loading: false, output: formatError(error) });
    }
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="status-area">
          {!isAuthenticated && (
            <button type="button" className="primary" onClick={() => void handleLogin()}>
              Login
            </button>
          )}
          <span className="status">{statusText}</span>
        </div>

        {isAuthenticated && (
          <a
            className="logout-link"
            href="#"
            onClick={(event) => {
              event.preventDefault();
              void handleLogout();
            }}
          >
            Logout
          </a>
        )}
      </header>

      {loginError && <p className="error">{loginError}</p>}

      {isAuthenticated && (
        <main className="panels">
          <section className="panel">
            <h2>Service A</h2>
            <button
              type="button"
              onClick={() => void loadServiceA()}
              disabled={serviceA.loading}
            >
              {serviceA.loading ? "Loading..." : "get data from service A"}
            </button>
            <textarea
              readOnly
              value={serviceA.output}
              placeholder="Service A response will appear here"
            />
          </section>

          <section className="panel">
            <h2>Service B (via Service A OBO)</h2>
            <button
              type="button"
              onClick={() => void loadServiceB()}
              disabled={serviceB.loading}
            >
              {serviceB.loading ? "Loading..." : "get data from service B"}
            </button>
            <textarea
              readOnly
              value={serviceB.output}
              placeholder="Service B response will appear here"
            />
          </section>
        </main>
      )}
    </div>
  );
}
