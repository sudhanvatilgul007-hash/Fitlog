export async function api<T = any>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const r = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    const error = await r
      .json()
      .catch(() => ({ detail: "Server unavailable" }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Please check the values you entered.",
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
