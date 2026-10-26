import { InteractionRequiredAuthError } from "@azure/msal-browser";
import { useMsal } from "@azure/msal-react";
import { useCallback } from "react";

import { serviceAScope } from "./authConfig";

export function useApiToken() {
  const { instance, accounts } = useMsal();

  return useCallback(async (): Promise<string> => {
    const account = instance.getActiveAccount() ?? accounts[0];
    if (!account) {
      throw new Error("No signed-in account. Please log in first.");
    }

    try {
      const result = await instance.acquireTokenSilent({
        scopes: [serviceAScope],
        account,
      });
      return result.accessToken;
    } catch (error) {
      if (error instanceof InteractionRequiredAuthError) {
        const result = await instance.acquireTokenPopup({
          scopes: [serviceAScope],
          account,
        });
        return result.accessToken;
      }
      throw error;
    }
  }, [accounts, instance]);
}
