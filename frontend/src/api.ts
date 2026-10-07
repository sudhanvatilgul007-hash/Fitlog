let csrfToken = "";
export function setCsrf(token: string) {
  csrfToken = token;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T = any>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const r = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    if (
      r.status === 401 &&
      !path.startsWith("/auth/") &&
      typeof window !== "undefined"
    )
      window.dispatchEvent(new Event("fitlog-session-expired"));
    const error = await r
      .json()
      .catch(() => ({ detail: "Server unavailable" }));
    throw new ApiError(
      typeof error.detail === "string"
        ? error.detail
        : "Please check the values you entered.",
      r.status,
    );
  }
  return r.json();
}
export function scaled(
  food: { baseQuantity: number; calories: number; proteinG: number },
  quantity: number,
) {
  return {
    calories: (food.calories * quantity) / food.baseQuantity,
    proteinG: (food.proteinG * quantity) / food.baseQuantity,
  };
}
export function localDate() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
