import { serviceABaseUrl } from "./authConfig";

export function serviceARequestUri(path: string): string {
  return `${serviceABaseUrl}${path}`;
}

export async function fetchFromServiceA(
  path: string,
  accessToken: string,
): Promise<string> {
  const response = await fetch(serviceARequestUri(path), {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  const body = await response.text();
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}\n${body}`);
  }

  return body;
}
