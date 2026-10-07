import { useState } from "react";
import { api, ApiError } from "./api";

type Preset = {
  name: string;
  baseQuantity: number;
  baseUnit: string;
  calories: number;
  proteinG: number;
  carbsG: number | null;
  fatG: number | null;
  fiberG: number | null;
  favorite: boolean;
  nutritionSource?: string;
  nutritionNotes?: string;
};
const nutrients = [
  ["calories", "Calories (kcal)"],
  ["proteinG", "Protein (g)"],
  ["carbsG", "Carbs (g)"],
  ["fatG", "Fat (g)"],
  ["fiberG", "Fiber (g, optional)"],
] as const;
export function FoodForm({
  food,
  busy,
  save,
}: {
  food: Preset | null;
  busy: boolean;
  save: (data: any) => Promise<boolean | undefined>;
}) {
  const [name, setName] = useState(food?.name ?? "");
  const [quantity, setQuantity] = useState(String(food?.baseQuantity ?? 100));
  const [unit, setUnit] = useState(food?.baseUnit ?? "g");
  const [details, setDetails] = useState("");
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      nutrients.map(([k]) => [k, food?.[k] == null ? "" : String(food[k])]),
    ),
  );
  const [source, setSource] = useState(food?.nutritionSource ?? "manual");
  const [notes, setNotes] = useState(food?.nutritionNotes ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(false);
  const [estimated, setEstimated] = useState(false);
  const [favorite, setFavorite] = useState(food?.favorite ?? true);
  function changeIdentity(change: () => void) {
    change();
    setError("");
    setRetry(false);
    setNotes("");
    setSource("manual");
    if (estimated)
      setValues(Object.fromEntries(nutrients.map(([k]) => [k, ""])));
    setEstimated(false);
  }
  async function estimate() {
    if (loading || busy) return;
    setLoading(true);
    setError("");
    try {
      const result = await api("/foods/estimate", "POST", {
        name,
        baseQuantity: Number(quantity),
        baseUnit: unit,
        details,
        retry,
      });
      setValues(
        Object.fromEntries(
          nutrients.map(([k]) => [
            k,
            result[k] == null ? "" : String(result[k]),
          ]),
        ),
      );
      setSource(result.source);
      setNotes(result.notes);
      setEstimated(true);
      setRetry(false);
    } catch (e) {
      setError((e as Error).message);
      setRetry(!(e instanceof ApiError) || e.status >= 500 || e.status === 409);
    } finally {
      setLoading(false);
    }
  }
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setError("");
        const data: any = {
          name: name.trim(),
          baseQuantity: Number(quantity),
          baseUnit: unit,
          favorite,
          nutritionSource: source,
          nutritionNotes: notes,
        };
        for (const [k] of nutrients)
          data[k] = values[k] === "" ? null : Number(values[k]);
        if (!(await save(data)))
          setError("Food could not be saved. Check the values and try again.");
      }}
    >
      <h2>{food ? "Edit food preset" : "Add a new food"}</h2>
      <p>
        Enter a food and portion, then estimate nutrition or use the package
        label. Saved foods are reused before AI is called.
      </p>
      <fieldset disabled={busy || loading} className="food-form-fields">
        <label>
          Food name
          <input
            name="name"
            required
            maxLength={120}
            placeholder="e.g. Paneer curry · cooked"
            value={name}
            onChange={(e) => changeIdentity(() => setName(e.target.value))}
          />
        </label>
        <div className="form-grid">
          <label>
            Base quantity
            <input
              name="baseQuantity"
              type="number"
              required
              min="0.01"
              max="100000"
              step="any"
              value={quantity}
              onChange={(e) =>
                changeIdentity(() => setQuantity(e.target.value))
              }
            />
          </label>
          <label>
            Unit
            <select
              name="baseUnit"
              value={unit}
              onChange={(e) => changeIdentity(() => setUnit(e.target.value))}
            >
              {[
                "g",
                "ml",
                "scoop",
                "slice",
                "piece",
                "serving",
                "tbsp",
                "tsp",
              ].map((u) => (
                <option key={u}>{u}</option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Preparation or brand (optional)
          <input
            name="details"
            maxLength={600}
            placeholder="e.g. homemade, cooked with 1 tsp oil"
            value={details}
            onChange={(e) => changeIdentity(() => setDetails(e.target.value))}
          />
        </label>
        <button
          type="button"
          className="button outline full"
          disabled={
            !name.trim() ||
            !Number(quantity) ||
            Number(quantity) <= 0 ||
            Number(quantity) > 100000
          }
          onClick={estimate}
        >
          {retry ? "Retry estimate" : "Estimate nutrition"}
        </button>
        <p className="nutrition-hint">
          If no saved match exists, this sends the food and portion to AI and
          may incur a small charge. Recipes and serving sizes vary; review the
          estimate before saving.
        </p>
        {notes && (
          <div className="nutrition-estimate" role="status">
            <strong>
              {source === "saved" ? "From saved food" : "AI estimate"}
            </strong>
            <p>{notes}</p>
            <small>
              Values below are for {quantity} {unit}. You can adjust them.
            </small>
          </div>
        )}
        <div className="form-grid">
          {nutrients.map(([k, label]) => (
            <label key={k}>
              {label}
              <input
                name={k}
                type="number"
                min="0"
                step="any"
                required={k === "calories" || k === "proteinG"}
                value={values[k]}
                onChange={(e) => {
                  setValues({ ...values, [k]: e.target.value });
                  setSource("manual");
                  setNotes("");
                }}
              />
            </label>
          ))}
        </div>
        <label className="checkbox">
          <input
            name="favorite"
            type="checkbox"
            checked={favorite}
            onChange={(e) => setFavorite(e.target.checked)}
          />
          Save as favorite
        </label>
        <button className="button dark full">
          {busy ? "Saving…" : "Save food"}
        </button>
      </fieldset>
      {loading && <p role="status">Estimating nutrition…</p>}
      {error && (
        <p className="nutrition-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
