import React, { useEffect, useState, lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Dumbbell,
  Flame,
  Footprints,
  History,
  Leaf,
  Minus,
  Plus,
  Settings as SettingsIcon,
  Sparkles,
  Star,
  Trash2,
  X,
} from "lucide-react";
const TrendChart = lazy(() => import("./TrendChart"));
import { api, scaled, localDate } from "./api";
import "./style.css";

type Food = {
  id: string;
  name: string;
  baseQuantity: number;
  baseUnit: string;
  calories: number;
  proteinG: number;
  carbsG: number | null;
  fatG: number | null;
  fiberG: number | null;
  favorite: boolean;
  active: boolean;
  sortOrder: number;
  usageCount: number;
  lastUsed: string;
};
const fmt = (n: number) => Math.round(n).toLocaleString();
const profileName = (s: string) =>
  ({
    sedentary: "Sedentary",
    high_walking: "High walking",
    gym_walking: "Gym + high walking",
    custom: "Custom",
  })[s] || s.replace(/_/g, " ");
const activityName = (s: string) => s.replace(/_/g, " ");
function App() {
  const [screen, setScreen] = useState("today"),
    [day, setDay] = useState(localDate()),
    [log, setLog] = useState<any>(null),
    [foods, setFoods] = useState<Food[]>([]),
    [settings, setSettings] = useState<any>(null),
    [history, setHistory] = useState<any>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [modal, setModal] = useState<
      | null
      | "food"
      | "custom"
      | "activity"
      | "analysis"
      | "confirm"
      | "editFood"
    >(null),
    [selected, setSelected] = useState<Food | null>(null),
    [quantity, setQuantity] = useState(1),
    [tab, setTab] = useState("Favorites"),
    [search, setSearch] = useState(""),
    [analysisError, setAnalysisError] = useState(false),
    [activityEdit, setActivityEdit] = useState<any>(null),
    [analysisVersions, setAnalysisVersions] = useState<any[]>([]);
  async function load() {
    try {
      const [l, f, s] = await Promise.all([
        api(`/logs/${day}`),
        api("/foods"),
        api("/settings"),
      ]);
      setLog(l);
      setFoods(f);
      setSettings(s);
      setAnalysisError(l.analysisAttempt === "failed");
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    setLog(null);
    setAnalysisError(false);
    load();
  }, [day]);
  useEffect(() => {
    if (screen === "history")
      api("/history?from=2000-01-01")
        .then(setHistory)
        .catch((e) => setError(e.message));
  }, [screen, log]);
  async function mutate(path: string, method: string, body?: unknown) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const l = await api(path, method, body);
      if (l.calculated) {
        setLog(l);
        setFoods(await api("/foods"));
      } else await load();
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function addFood(
    food: Food,
    q = food.baseUnit === "g" || food.baseUnit === "ml" ? 100 : 1,
  ) {
    return mutate(`/logs/${day}/foods`, "POST", {
      foodPresetId: food.id,
      quantity: q,
      unit: food.baseUnit,
    });
  }
  async function showAnalysis() {
    setModal("analysis");
    try {
      setAnalysisVersions(await api(`/logs/${day}/analysis`));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function analyze(confirmed = false) {
    setModal(null);
    setBusy(true);
    setError("");
    try {
      await api(`/logs/${day}/analyze`, "POST", {
        confirmReanalysis: confirmed,
        retry: analysisError || log?.analysisAttempt === "failed",
      });
      await load();
      setAnalysisError(false);
      await showAnalysis();
    } catch (e) {
      setAnalysisError(true);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const total = log?.calculated;
  const todayLabel = new Date(`${day}T12:00:00`).toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  function shiftDate(n: number) {
    const d = new Date(`${day}T12:00:00`);
    d.setDate(d.getDate() + n);
    setDay(
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`,
    );
  }
  return (
    <div className="app">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setScreen("today");
          }}
        >
          <span className="brand-icon">
            <Activity size={22} />
          </span>
          fitlog<span className="brand-dot">.</span>
        </a>
        <span className="nav-caption">YOUR DAILY PRACTICE</span>
        <nav>
          {[
            ["today", Activity, "Today"],
            ["history", History, "History & trends"],
            ["settings", SettingsIcon, "Settings"],
          ].map(([id, Icon, label]: any) => (
            <button
              key={id}
              className={screen === id ? "nav-item active" : "nav-item"}
              onClick={() => setScreen(id)}
            >
              <Icon size={19} />
              {label}
              {screen === id && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <Leaf size={24} />
          <h3>Small steps. Real progress.</h3>
          <p>A little consistency goes a long way. Make today count.</p>
        </div>
        <div className="profile">
          <span>ST</span>
          <div>
            Personal journal<small>Your space to get stronger</small>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span className="mobile-brand">fitlog.</span>
          <span className="breadcrumb">
            Your journal <ChevronRight size={14} />{" "}
            {screen === "today"
              ? "Daily overview"
              : screen === "history"
                ? "History & trends"
                : "Settings"}
          </span>
          <span className="private-label">
            <span /> Personal workspace
          </span>
        </header>
        <div className="content">
          {error && (
            <div role="alert" className="error">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {screen === "today" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">ONE DAY AT A TIME</div>
                  <h1>
                    {day === localDate()
                      ? "Let’s make today count."
                      : "Your daily journal."}
                  </h1>
                  <p>Log a little. Learn a lot. Keep moving forward.</p>
                </div>
                <div className="date-control">
                  <button
                    aria-label="Previous day"
                    onClick={() => shiftDate(-1)}
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <label>
                    {todayLabel}
                    <input
                      aria-label="Log date"
                      type="date"
                      value={day}
                      onChange={(e) => setDay(e.target.value)}
                    />
                  </label>
                  <button aria-label="Next day" onClick={() => shiftDate(1)}>
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>
              {!log ? (
                <div className="empty">
                  {error
                    ? "Start the fitlog API, run migrations and seed, then reload."
                    : "Loading your journal…"}
                  <button onClick={load}>Reload</button>
                </div>
              ) : (
                <>
                  <div className="day-strip">
                    <label>
                      <span className="weight-icon">↟</span>Body weight{" "}
                      <input
                        key={day + log.weightKg}
                        type="number"
                        aria-label="Body weight"
                        min={settings?.weightMinKg}
                        max={settings?.weightMaxKg}
                        step="0.1"
                        defaultValue={log.weightKg}
                        onBlur={(e) => {
                          if (+e.target.value !== log.weightKg)
                            mutate(`/logs/${day}/weight`, "PUT", {
                              weightKg: +e.target.value,
                            });
                        }}
                      />{" "}
                      kg
                    </label>
                    <span className="strip-divider" />
                    <span>
                      Protein goal{" "}
                      <b>
                        {settings.proteinMinG}–{settings.proteinMaxG} g
                      </b>
                    </span>
                    <span>
                      Deficit goal{" "}
                      <b>
                        {settings.deficitMinKcal}–{settings.deficitMaxKcal} kcal
                      </b>
                    </span>
                  </div>
                  <div className="stats">
                    <Metric
                      title="Calories eaten"
                      value={fmt(total.totalCalories)}
                      unit="kcal"
                      icon={<Flame size={19} />}
                      text="Fuel for your day"
                      progress={Math.min(
                        100,
                        (total.totalCalories / log.calculated.selectedTDEE) *
                          100,
                      )}
                      color="orange"
                    />
                    <Metric
                      title="Protein"
                      value={fmt(total.totalProteinG)}
                      unit="g"
                      icon={<Dumbbell size={19} />}
                      text={`${Math.max(0, Math.round(settings.proteinMinG - total.totalProteinG))} g to your minimum goal`}
                      progress={Math.min(
                        100,
                        (total.totalProteinG / settings.proteinMinG) * 100,
                      )}
                      color="green"
                    />
                    <Metric
                      title="Estimated TDEE"
                      value={fmt(total.selectedTDEE)}
                      unit="kcal"
                      icon={<Activity size={19} />}
                      text={profileName(log.profile)}
                      color="purple"
                    />
                    <Metric
                      title="Current deficit"
                      value={fmt(total.deficitKcal)}
                      unit="kcal"
                      icon={<ArrowUpRight size={19} />}
                      text={
                        total.deficitKcal > settings.deficitMaxKcal
                          ? "Above target range"
                          : total.deficitKcal < settings.deficitMinKcal
                            ? "Below target range"
                            : "Within your target range"
                      }
                      color="blue"
                    />
                  </div>
                  <div className="dashboard-grid">
                    <section className="card food-card">
                      <div className="section-heading">
                        <div>
                          <h2>
                            Food journal{" "}
                            <span className="count">{log.food.length}</span>
                          </h2>
                          <p>Good nutrition starts with a simple log.</p>
                        </div>
                        <button
                          className="button dark small"
                          disabled={busy}
                          onClick={() => {
                            setSelected(null);
                            setModal("food");
                          }}
                        >
                          <Plus size={16} />
                          Add food
                        </button>
                      </div>
                      <div className="subheading">
                        YOUR GO-TO FOODS <span>Tap + for a quick add</span>
                      </div>
                      <div className="quick-foods">
                        {foods
                          .filter((f) => f.favorite)
                          .slice(0, 6)
                          .map((f, i) => (
                            <div className="quick-food" key={f.id}>
                              <button
                                className="food-preset"
                                onClick={() => {
                                  setSelected(f);
                                  setQuantity(
                                    ["g", "ml"].includes(f.baseUnit) ? 100 : 1,
                                  );
                                  setModal("food");
                                }}
                              >
                                <span
                                  className={`food-emoji food-color-${i % 4}`}
                                >
                                  {["🥛", "🫐", "🍞", "🧀", "🥜", "🌱"][i % 6]}
                                </span>
                                <span>
                                  {f.name}
                                  <small>
                                    {fmt(f.calories)} kcal · {f.baseQuantity}{" "}
                                    {f.baseUnit}
                                  </small>
                                </span>
                              </button>
                              <button
                                aria-label={`Quick add ${f.name}`}
                                className="quick-plus"
                                disabled={busy}
                                onClick={() => addFood(f)}
                              >
                                <Plus size={16} />
                              </button>
                            </div>
                          ))}
                      </div>
                      <div className="journal-header">
                        <span>LOGGED TODAY</span>
                        <span>CALORIES / PROTEIN</span>
                      </div>
                      <div className="entries">
                        {log.food.length === 0 ? (
                          <div className="empty-log">
                            <span>🍽️</span>
                            <h3>Your plate is a blank canvas.</h3>
                            <p>Add your first meal with a favorite above.</p>
                          </div>
                        ) : (
                          log.food.map((f: any) => (
                            <div className="food-row" key={f.id}>
                              <div className="entry-name">
                                <b>{f.displayName}</b>
                                <small>
                                  {f.quantity} {f.unit}
                                </small>
                              </div>
                              <div className="quantity-controls">
                                <button
                                  aria-label={`Decrease ${f.displayName}`}
                                  disabled={
                                    busy ||
                                    f.quantity <= (f.unit === "g" ? 10 : 1)
                                  }
                                  onClick={() =>
                                    mutate(
                                      `/logs/${day}/foods/${f.id}`,
                                      "PATCH",
                                      {
                                        quantity:
                                          f.quantity -
                                          (f.unit === "g" ? 10 : 1),
                                        unit: f.unit,
                                      },
                                    )
                                  }
                                >
                                  <Minus size={13} />
                                </button>
                                <input
                                  type="number"
                                  aria-label={`Quantity of ${f.displayName}`}
                                  key={f.id + f.quantity}
                                  defaultValue={f.quantity}
                                  min="0.01"
                                  step="any"
                                  onBlur={(e) => {
                                    if (+e.target.value !== f.quantity)
                                      mutate(
                                        `/logs/${day}/foods/${f.id}`,
                                        "PATCH",
                                        {
                                          quantity: +e.target.value,
                                          unit: f.unit,
                                        },
                                      );
                                  }}
                                />
                                <button
                                  aria-label={`Increase ${f.displayName}`}
                                  disabled={busy}
                                  onClick={() =>
                                    mutate(
                                      `/logs/${day}/foods/${f.id}`,
                                      "PATCH",
                                      {
                                        quantity:
                                          f.quantity +
                                          (f.unit === "g" ? 10 : 1),
                                        unit: f.unit,
                                      },
                                    )
                                  }
                                >
                                  <Plus size={13} />
                                </button>
                              </div>
                              <div className="entry-totals">
                                <b>
                                  {fmt(f.calories)} <small>kcal</small>
                                </b>
                                <span>
                                  {Math.round(f.proteinG * 10) / 10} g protein
                                </span>
                              </div>
                              <button
                                className="delete"
                                aria-label={`Remove ${f.displayName}`}
                                disabled={busy}
                                onClick={() =>
                                  mutate(`/logs/${day}/foods/${f.id}`, "DELETE")
                                }
                              >
                                <X size={15} />
                              </button>
                            </div>
                          ))
                        )}
                      </div>
                      <footer className="food-footer">
                        <span>Daily total</span>
                        <b>
                          {fmt(total.totalCalories)} kcal <span>·</span>{" "}
                          {Math.round(total.totalProteinG * 10) / 10} g protein
                        </b>
                      </footer>
                      {log.food.length > 0 && (
                        <p className="macro-note">
                          Carbs {fmt(total.carbsG)} g · Fat {fmt(total.fatG)} g
                          {(!total.carbsGComplete || !total.fatGComplete) &&
                            " · Partial totals: some labels are missing macros"}
                        </p>
                      )}
                    </section>
                    <div className="right-column">
                      <section className="card activity-card">
                        <div className="section-heading">
                          <div>
                            <h2>
                              <Footprints size={20} />
                              Walking & activity
                            </h2>
                            <p>Every step adds up.</p>
                          </div>
                          <button
                            aria-label="Add activity"
                            className="icon-button"
                            onClick={() => {
                              setActivityEdit(null);
                              setModal("activity");
                            }}
                          >
                            <Plus size={18} />
                          </button>
                        </div>
                        <form
                          className="walking-form"
                          onSubmit={async (e) => {
                            e.preventDefault();
                            const form = e.currentTarget;
                            const f = new FormData(form);
                            const saved = await mutate(
                              `/logs/${day}/activities`,
                              "POST",
                              {
                                type: "walking",
                                distanceKm: Number(f.get("distance")),
                                durationMinutes: f.get("minutes")
                                  ? Number(f.get("minutes"))
                                  : null,
                                steps: f.get("steps")
                                  ? Number(f.get("steps"))
                                  : null,
                              },
                            );
                            if (saved) form.reset();
                          }}
                        >
                          <label>
                            Distance{" "}
                            <div className="input-unit">
                              <input
                                name="distance"
                                aria-label="Walking distance"
                                required
                                type="number"
                                min="0.01"
                                step="0.01"
                                placeholder="0.00"
                              />
                              <span>km</span>
                            </div>
                          </label>
                          <label>
                            Duration{" "}
                            <div className="input-unit">
                              <input
                                name="minutes"
                                aria-label="Walking duration"
                                type="number"
                                min="1"
                                step="any"
                                placeholder="Optional"
                              />
                              <span>min</span>
                            </div>
                          </label>
                          <label className="steps-input">
                            Steps{" "}
                            <input
                              name="steps"
                              type="number"
                              min="0"
                              step="1"
                              placeholder="Optional"
                            />
                          </label>
                          <button className="button outline" disabled={busy}>
                            <Plus size={15} />
                            Log walk
                          </button>
                        </form>
                        <div className="burn">
                          <span>Estimated walking burn</span>
                          <b>
                            {fmt(total.walkingCaloriesEstimate)}{" "}
                            <small>kcal</small>
                          </b>
                        </div>
                        {log.activity
                          .filter(
                            (a: any) =>
                              a.type === "walking" || a.type === "manual",
                          )
                          .map((a: any) => (
                            <ActivityRow
                              key={a.id}
                              a={a}
                              busy={busy}
                              edit={() => {
                                setActivityEdit(a);
                                setModal("activity");
                              }}
                              remove={() =>
                                mutate(
                                  `/logs/${day}/activities/${a.id}`,
                                  "DELETE",
                                )
                              }
                            />
                          ))}
                        <small className="formula">
                          {settings.walkingCoefficient} × {log.weightKg} kg ×
                          distance in km
                        </small>
                      </section>
                      <section className="card gym-card">
                        <div className="section-heading">
                          <div>
                            <h2>
                              <Dumbbell size={19} />
                              Gym session
                            </h2>
                            <p>A stronger you, one session at a time.</p>
                          </div>
                        </div>
                        <div className="gym-presets">
                          {[
                            "cycling",
                            "treadmill",
                            "upper_body",
                            "pull",
                            "push",
                            "legs",
                            "abs",
                          ].map((t) => (
                            <button
                              key={t}
                              onClick={() => {
                                setActivityEdit({ type: t });
                                setModal("activity");
                              }}
                            >
                              <Plus size={13} />
                              {activityName(t)}
                            </button>
                          ))}
                        </div>
                        {log.activity
                          .filter(
                            (a: any) => !["walking", "manual"].includes(a.type),
                          )
                          .map((a: any) => (
                            <ActivityRow
                              key={a.id}
                              a={a}
                              busy={busy}
                              edit={() => {
                                setActivityEdit(a);
                                setModal("activity");
                              }}
                              remove={() =>
                                mutate(
                                  `/logs/${day}/activities/${a.id}`,
                                  "DELETE",
                                )
                              }
                            />
                          ))}
                        <div className="burn">
                          <span>Estimated exercise burn</span>
                          <b>
                            {fmt(total.exerciseCaloriesEstimate)}{" "}
                            <small>kcal</small>
                          </b>
                        </div>
                      </section>
                      <section className="card expenditure">
                        <h2>Daily expenditure</h2>
                        <label>
                          Activity profile
                          <select
                            value={log.profile}
                            onChange={(e) => {
                              if (e.target.value === "custom")
                                mutate(`/logs/${day}/tdee`, "PUT", {
                                  profile: "custom",
                                  kcal: total.selectedTDEE,
                                });
                              else
                                mutate(`/logs/${day}/tdee`, "PUT", {
                                  profile: e.target.value,
                                });
                            }}
                          >
                            {Object.entries(settings.tdeeProfiles).map(
                              ([k, v]) => (
                                <option key={k} value={k}>
                                  {profileName(k)} · {String(v)} kcal
                                </option>
                              ),
                            )}
                            <option value="custom">Custom override</option>
                          </select>
                        </label>
                        {log.profile === "custom" && (
                          <label>
                            TDEE kcal
                            <input
                              type="number"
                              defaultValue={total.selectedTDEE}
                              min="500"
                              max="10000"
                              onBlur={(e) =>
                                mutate(`/logs/${day}/tdee`, "PUT", {
                                  profile: "custom",
                                  kcal: +e.target.value,
                                })
                              }
                            />
                          </label>
                        )}
                        <p>
                          <Check size={15} />
                          Activity is included in your selected TDEE. Burn
                          estimates aren’t added again.
                        </p>
                      </section>
                    </div>
                  </div>
                  <div className="analysis-banner">
                    <span className="sparkle-box">
                      <Sparkles size={22} />
                    </span>
                    <div>
                      <h3>
                        {log.analysis
                          ? log.analysis.stale
                            ? "Your log has changed."
                            : "Your daily reflection is ready."
                          : "Ready for your daily reflection?"}
                      </h3>
                      <p>
                        {log.analysis?.stale
                          ? "Analysis is based on an older snapshot. Re-analyze when you’re ready."
                          : "AI looks at your completed day. Logging and totals use no AI calls."}
                      </p>
                    </div>
                    {log.analysis && (
                      <button className="button outline" onClick={showAnalysis}>
                        Show analysis
                      </button>
                    )}
                    {(!log.analysis || log.analysis.stale || analysisError) && (
                      <button
                        className="button dark"
                        disabled={busy}
                        onClick={() =>
                          log.analysis ? setModal("confirm") : analyze(false)
                        }
                      >
                        <Sparkles size={16} />
                        {busy
                          ? "Working…"
                          : analysisError
                            ? "Retry analysis"
                            : log.analysis
                              ? "Re-analyze"
                              : "Analyze day"}
                      </button>
                    )}
                  </div>
                  <p className="bottom-note">
                    Your numbers, made simple. Estimates are a guide,
                    consistency is the goal.
                  </p>
                </>
              )}
            </>
          )}
          {screen === "history" && (
            <>
              <div className="eyebrow">THE BIGGER PICTURE</div>
              <h1>Progress over perfection.</h1>
              <p className="intro">
                Your history and averages, calculated from your journal.
              </p>
              {history && (
                <>
                  <div className="stats">
                    {[
                      ["7-day avg. calories", "totalCalories", "kcal"],
                      ["7-day avg. protein", "totalProteinG", "g"],
                      ["7-day avg. deficit", "deficitKcal", "kcal"],
                      ["30-day avg. weight", "weightKg", "kg"],
                    ].map(([title, key, unit]) => (
                      <Metric
                        key={title}
                        title={title}
                        value={String(
                          (title.startsWith("30")
                            ? history.thirtyDay
                            : history.sevenDay)[key] ?? "—",
                        )}
                        unit={unit}
                        text="Logged days only"
                        color="green"
                        icon={<History size={18} />}
                      />
                    ))}
                  </div>
                  <p>
                    {history.proteinAdherence.meeting} of{" "}
                    {history.proteinAdherence.total} logged days met your
                    current protein minimum.
                  </p>
                  <div className="trend-grid">
                    {[
                      ["Weight trend", "weightKg", "kg"],
                      ["Deficit trend", "deficitKcal", "kcal"],
                    ].map(([title, key, unit]) => (
                      <section className="card" key={key}>
                        <h2>{title}</h2>
                        <div className="chart">
                          <Suspense fallback={<p>Loading chart…</p>}>
                            <TrendChart
                              days={history.days}
                              metric={key}
                              unit={unit}
                            />
                          </Suspense>
                        </div>
                      </section>
                    ))}
                  </div>
                  <section className="card history-table">
                    <h2>Daily journal</h2>
                    {!history.days.length && (
                      <p>Start logging to see your history.</p>
                    )}
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Day</th>
                            <th>Weight</th>
                            <th>Calories</th>
                            <th>Protein</th>
                            <th>TDEE</th>
                            <th>Deficit</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[...history.days].reverse().map((d: any) => (
                            <tr
                              key={d.date}
                              onClick={() => {
                                setDay(d.date);
                                setScreen("today");
                              }}
                            >
                              <td>
                                <button>
                                  {d.date}
                                  <ArrowUpRight size={14} />
                                </button>
                              </td>
                              <td>{d.weightKg} kg</td>
                              <td>{fmt(d.totalCalories)}</td>
                              <td>{fmt(d.totalProteinG)} g</td>
                              <td>{fmt(d.selectedTDEE)}</td>
                              <td>{fmt(d.deficitKcal)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                </>
              )}
            </>
          )}
          {screen === "settings" && settings && (
            <>
              <div className="eyebrow">MAKE IT YOURS</div>
              <h1>Your goals. Your defaults.</h1>
              <p className="intro">
                Tune your targets and the foods you reach for most.
              </p>
              <form
                className="card settings-form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  const s = {
                    ...settings,
                    tdeeProfiles: { ...settings.tdeeProfiles },
                  };
                  for (const key of [
                    "proteinMinG",
                    "proteinMaxG",
                    "deficitMinKcal",
                    "deficitMaxKcal",
                    "walkingCoefficient",
                    "weightMinKg",
                    "weightMaxKg",
                  ])
                    s[key] = Number(f.get(key));
                  for (const k of Object.keys(s.tdeeProfiles))
                    s.tdeeProfiles[k] = Number(f.get("profile_" + k));
                  await mutate("/settings", "PUT", s);
                }}
              >
                <h2>Targets & calculations</h2>
                <div className="settings-grid">
                  {[
                    ["proteinMinG", "Protein minimum (g)"],
                    ["proteinMaxG", "Protein maximum (g)"],
                    ["deficitMinKcal", "Deficit minimum (kcal)"],
                    ["deficitMaxKcal", "Deficit maximum (kcal)"],
                    ["walkingCoefficient", "Walking coefficient"],
                    ["weightMinKg", "Minimum weight (kg)"],
                    ["weightMaxKg", "Maximum weight (kg)"],
                  ].map(([k, l]) => (
                    <label key={k}>
                      {l}
                      <input
                        name={k}
                        type="number"
                        step="any"
                        required
                        defaultValue={settings[k]}
                      />
                    </label>
                  ))}
                  {Object.keys(settings.tdeeProfiles).map((k) => (
                    <label key={k}>
                      {profileName(k)} TDEE (kcal)
                      <input
                        name={"profile_" + k}
                        type="number"
                        min="500"
                        max="10000"
                        required
                        defaultValue={settings.tdeeProfiles[k]}
                      />
                    </label>
                  ))}
                </div>
                <button disabled={busy} className="button dark">
                  Save settings
                </button>
              </form>
              <section className="card">
                <div className="section-heading">
                  <div>
                    <h2>Food presets</h2>
                    <p>
                      Recipe estimates are editable. Use your package labels
                      when available.
                    </p>
                  </div>
                  <button
                    className="button dark"
                    onClick={() => {
                      setSelected(null);
                      setModal("custom");
                    }}
                  >
                    <Plus size={16} />
                    Custom food
                  </button>
                </div>
                {[...foods]
                  .sort((a, b) => a.sortOrder - b.sortOrder)
                  .map((f, i) => (
                    <div className="preset-row" key={f.id}>
                      <button
                        className={f.favorite ? "favorite yes" : "favorite"}
                        aria-label={`Favorite ${f.name}`}
                        onClick={() =>
                          mutate(`/foods/${f.id}`, "PATCH", {
                            favorite: !f.favorite,
                          })
                        }
                      >
                        <Star size={18} />
                      </button>
                      <div>
                        <b>{f.name}</b>
                        <small>
                          {f.calories} kcal · {f.proteinG} g protein /{" "}
                          {f.baseQuantity} {f.baseUnit}
                        </small>
                      </div>
                      <button
                        aria-label={`Move ${f.name} up`}
                        disabled={i === 0 || busy}
                        onClick={async () => {
                          const sorted = [...foods].sort(
                            (a, b) => a.sortOrder - b.sortOrder,
                          );
                          const prev = sorted[i - 1];
                          await api(`/foods/${prev.id}`, "PATCH", {
                            sortOrder: f.sortOrder,
                          });
                          await mutate(`/foods/${f.id}`, "PATCH", {
                            sortOrder: prev.sortOrder,
                          });
                        }}
                      >
                        ↑
                      </button>
                      <button
                        onClick={() => {
                          setSelected(f);
                          setModal("editFood");
                        }}
                      >
                        Edit
                      </button>
                      <button
                        aria-label={`Delete preset ${f.name}`}
                        onClick={() => mutate(`/foods/${f.id}`, "DELETE")}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))}
              </section>
            </>
          )}
        </div>
      </main>
      {screen === "today" && log && (
        <button
          className="mobile-analyze button dark"
          disabled={busy}
          onClick={() =>
            log.analysis && !log.analysis.stale && !analysisError
              ? showAnalysis()
              : log.analysis
                ? setModal("confirm")
                : analyze(false)
          }
        >
          <Sparkles size={17} />
          {busy
            ? "Working…"
            : analysisError
              ? "Retry analysis"
              : log.analysis && !log.analysis.stale
                ? "Show analysis"
                : log.analysis
                  ? "Re-analyze"
                  : "Analyze day"}
        </button>
      )}
      <nav className="mobile-nav">
        {[
          ["today", Activity, "Today"],
          ["history", History, "History"],
          ["settings", SettingsIcon, "Settings"],
        ].map(([id, Icon, label]: any) => (
          <button
            key={id}
            className={screen === id ? "active" : ""}
            onClick={() => setScreen(id)}
          >
            <Icon size={20} />
            {label}
          </button>
        ))}
      </nav>
      {modal && (
        <div className="overlay" onClick={() => setModal(null)}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={
              modal === "food"
                ? "Add food"
                : modal === "activity"
                  ? "Add activity"
                  : "fitlog dialog"
            }
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close"
              aria-label="Close dialog"
              onClick={() => setModal(null)}
            >
              <X size={20} />
            </button>
            {modal === "food" && (
              <>
                <div className="eyebrow">FUEL YOUR DAY</div>
                <h2>{selected ? selected.name : "Add to your journal"}</h2>
                {selected ? (
                  <>
                    <p>
                      Nutrition per {selected.baseQuantity} {selected.baseUnit}:{" "}
                      {selected.calories} kcal · {selected.proteinG} g protein
                    </p>
                    <div className="quantity-sheet">
                      <button
                        onClick={() =>
                          setQuantity(
                            Math.max(
                              0.1,
                              quantity -
                                (["g", "ml"].includes(selected.baseUnit)
                                  ? 10
                                  : 1),
                            ),
                          )
                        }
                      >
                        <Minus />
                      </button>
                      <label>
                        <input
                          aria-label="Food quantity"
                          type="number"
                          min="0.01"
                          step="any"
                          value={quantity}
                          onChange={(e) => setQuantity(+e.target.value)}
                        />
                        {selected.baseUnit}
                      </label>
                      <button
                        onClick={() =>
                          setQuantity(
                            quantity +
                              (["g", "ml"].includes(selected.baseUnit)
                                ? 10
                                : 1),
                          )
                        }
                      >
                        <Plus />
                      </button>
                    </div>
                    <div className="preview">
                      {fmt(scaled(selected, quantity).calories)} kcal{" "}
                      <span>·</span>{" "}
                      {Math.round(scaled(selected, quantity).proteinG * 10) /
                        10}{" "}
                      g protein
                    </div>
                    <button
                      className="button dark full"
                      disabled={busy || quantity <= 0}
                      onClick={async () => {
                        if (await addFood(selected, quantity)) setModal(null);
                      }}
                    >
                      Add food
                    </button>
                    <button
                      className="text-button"
                      onClick={() => setSelected(null)}
                    >
                      Back to foods
                    </button>
                  </>
                ) : (
                  <>
                    <div className="tabs">
                      {["Favorites", "Recent", "All foods"].map((t) => (
                        <button
                          className={t === tab ? "active" : ""}
                          key={t}
                          onClick={() => setTab(t)}
                        >
                          {t}
                        </button>
                      ))}
                      <button
                        onClick={() => {
                          setSelected(null);
                          setModal("custom");
                        }}
                      >
                        Add custom
                      </button>
                    </div>
                    <input
                      className="search"
                      aria-label="Search food"
                      placeholder="Search your foods…"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                    <div className="food-picker">
                      {foods
                        .filter(
                          (f) =>
                            f.name
                              .toLowerCase()
                              .includes(search.toLowerCase()) &&
                            (tab !== "Favorites" || f.favorite) &&
                            (tab !== "Recent" || f.lastUsed),
                        )
                        .sort((a, b) =>
                          tab === "Recent"
                            ? b.lastUsed.localeCompare(a.lastUsed)
                            : 0,
                        )
                        .map((f) => (
                          <button
                            key={f.id}
                            onClick={() => {
                              setSelected(f);
                              setQuantity(
                                ["g", "ml"].includes(f.baseUnit) ? 100 : 1,
                              );
                            }}
                          >
                            <span>
                              {f.name}
                              <small>
                                {f.calories} kcal · {f.proteinG} g /{" "}
                                {f.baseQuantity} {f.baseUnit}
                              </small>
                            </span>
                            <Plus size={17} />
                          </button>
                        ))}
                    </div>
                  </>
                )}
              </>
            )}
            {(modal === "custom" || modal === "editFood") && (
              <FoodForm
                food={modal === "editFood" ? selected : null}
                busy={busy}
                save={async (data) => {
                  if (
                    await mutate(
                      selected && modal === "editFood"
                        ? `/foods/${selected.id}`
                        : "/foods",
                      modal === "editFood" ? "PATCH" : "POST",
                      data,
                    )
                  )
                    setModal(null);
                }}
              />
            )}
            {modal === "activity" && (
              <ActivityForm
                key={activityEdit?.id || activityEdit?.type}
                activity={activityEdit}
                busy={busy}
                save={async (data) => {
                  if (
                    await mutate(
                      `/logs/${day}/activities${activityEdit?.id ? "/" + activityEdit.id : ""}`,
                      activityEdit?.id ? "PATCH" : "POST",
                      data,
                    )
                  )
                    setModal(null);
                }}
              />
            )}
            {modal === "confirm" && (
              <>
                <Sparkles className="green-icon" size={30} />
                <h2>Analyze this day again?</h2>
                <p>
                  This sends a new request to your AI provider and may incur a
                  charge. Your previous analysis stays in your journal.
                </p>
                <button
                  className="button dark full"
                  onClick={() => analyze(true)}
                >
                  Confirm re-analysis
                </button>
                <button className="text-button" onClick={() => setModal(null)}>
                  Cancel
                </button>
              </>
            )}
            {modal === "analysis" && (
              <>
                <div className="eyebrow">YOUR DAILY REFLECTION</div>
                <h2>Day analysis</h2>
                {!analysisVersions.length ? (
                  <p>No completed analysis is stored yet.</p>
                ) : (
                  analysisVersions.map((a: any, i: number) => (
                    <article className="analysis-result" key={a.id}>
                      <h3>
                        {i === 0 ? "Latest reflection" : "Earlier reflection"}{" "}
                        <span className="score">{a.response.dayScore}/10</span>
                      </h3>
                      {a.stale && (
                        <p className="stale">
                          Analysis is based on an older snapshot.
                        </p>
                      )}
                      <p>{a.response.summary}</p>
                      {[
                        ["Protein", "proteinAssessment"],
                        ["Deficit", "deficitAssessment"],
                        ["Activity", "activityAssessment"],
                      ].map(([title, k]) => (
                        <div key={k}>
                          <h4>{title}</h4>
                          <p>{a.response[k]}</p>
                        </div>
                      ))}
                      {[
                        ["Warnings", "warnings"],
                        ["Recommendations", "recommendations"],
                        ["Confidence notes", "confidenceNotes"],
                      ].map(
                        ([title, k]) =>
                          a.response[k].length > 0 && (
                            <div key={k}>
                              <h4>{title}</h4>
                              <ul>
                                {a.response[k].map((s: string, j: number) => (
                                  <li key={j}>{s}</li>
                                ))}
                              </ul>
                            </div>
                          ),
                      )}
                      <div className="snapshot-summary">
                        Analyzed snapshot:{" "}
                        {fmt(a.snapshot.calculated.totalCalories)} kcal ·{" "}
                        {a.snapshot.calculated.totalProteinG} g protein ·{" "}
                        {fmt(a.snapshot.calculated.deficitKcal)} kcal deficit
                      </div>
                      <small>
                        {a.provider} · {a.model} · prompt v{a.promptVersion} ·{" "}
                        {new Date(a.createdAt).toLocaleString()}
                      </small>
                    </article>
                  ))
                )}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
function Metric({
  title,
  value,
  unit,
  icon,
  text,
  color,
  progress,
}: {
  title: string;
  value: string;
  unit: string;
  icon: React.ReactNode;
  text: string;
  color: string;
  progress?: number;
}) {
  return (
    <section className={`metric ${color}`}>
      <div className="metric-heading">
        {title}
        <span>{icon}</span>
      </div>
      <div className="metric-value">
        {value}
        <small>{unit}</small>
      </div>
      {progress !== undefined && (
        <div className="progress">
          <span style={{ width: `${progress}%` }} />
        </div>
      )}
      <p>{text}</p>
    </section>
  );
}
function ActivityRow({
  a,
  busy,
  edit,
  remove,
}: {
  a: any;
  busy: boolean;
  edit: () => void;
  remove: () => void;
}) {
  return (
    <div className="activity-row">
      <button onClick={edit}>
        <b>{activityName(a.type)}</b>
        <small>
          {a.distanceKm ? `${a.distanceKm} km · ` : ""}
          {a.durationMinutes ? `${a.durationMinutes} min · ` : ""}
          {a.exerciseCount ? `${a.exerciseCount} exercises · ` : ""}
          {a.steps ? `${a.steps} steps · ` : ""}
          {a.speedKmh ? `${a.speedKmh} km/h · ` : ""}
          {fmt(a.caloriesEstimate)} kcal est.
        </small>
      </button>
      <button aria-label={`Remove ${a.type}`} disabled={busy} onClick={remove}>
        <X size={14} />
      </button>
    </div>
  );
}
function FoodForm({
  food,
  busy,
  save,
}: {
  food: Food | null;
  busy: boolean;
  save: (data: any) => void;
}) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        const data: any = {
          name: f.get("name"),
          baseUnit: f.get("baseUnit"),
          favorite: f.get("favorite") === "on",
        };
        for (const k of ["baseQuantity", "calories", "proteinG"])
          data[k] = Number(f.get(k));
        for (const k of ["carbsG", "fatG", "fiberG"])
          data[k] = f.get(k) ? Number(f.get(k)) : null;
        save(data);
      }}
    >
      <h2>{food ? "Edit food preset" : "Create a custom food"}</h2>
      <p>
        Use nutrition from the label. Historical entries keep their original
        values.
      </p>
      <label>
        Food name
        <input name="name" required defaultValue={food?.name} />
      </label>
      <div className="form-grid">
        <label>
          Base quantity
          <input
            name="baseQuantity"
            required
            type="number"
            min="0.01"
            step="any"
            defaultValue={food?.baseQuantity || 1}
          />
        </label>
        <label>
          Unit
          <select name="baseUnit" defaultValue={food?.baseUnit || "serving"}>
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
        {[
          ["calories", "Calories (kcal)"],
          ["proteinG", "Protein (g)"],
          ["carbsG", "Carbs (g, optional)"],
          ["fatG", "Fat (g, optional)"],
          ["fiberG", "Fiber (g, optional)"],
        ].map(([k, l]) => (
          <label key={k}>
            {l}
            <input
              name={k}
              required={["calories", "proteinG"].includes(k)}
              type="number"
              min="0"
              step="any"
              defaultValue={(food as any)?.[k] ?? ""}
            />
          </label>
        ))}
      </div>
      <label className="checkbox">
        <input
          name="favorite"
          type="checkbox"
          defaultChecked={food?.favorite ?? true}
        />
        Save as favorite
      </label>
      <button disabled={busy} className="button dark full">
        Save food
      </button>
    </form>
  );
}
function ActivityForm({
  activity,
  busy,
  save,
}: {
  activity: any;
  busy: boolean;
  save: (data: any) => void;
}) {
  const [type, setType] = useState(activity?.type || "walking");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        const data: any = { type };
        for (const k of [
          "distanceKm",
          "durationMinutes",
          "speedKmh",
          "exerciseCount",
          "steps",
          "caloriesEstimate",
        ])
          if (f.get(k)) data[k] = Number(f.get(k));
        save(data);
      }}
    >
      <h2>{activity?.id ? "Edit activity" : "Add activity"}</h2>
      <p>Exercise estimates are informational and never added to your TDEE.</p>
      <label>
        Activity
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {[
            "walking",
            "cycling",
            "treadmill",
            "upper_body",
            "pull",
            "push",
            "legs",
            "abs",
            "manual",
          ].map((t) => (
            <option value={t} key={t}>
              {activityName(t)}
            </option>
          ))}
        </select>
      </label>
      {type === "walking" && (
        <>
          <label>
            Distance (km)
            <input
              name="distanceKm"
              required
              type="number"
              step="any"
              min="0.01"
              defaultValue={activity?.distanceKm}
            />
          </label>
          <label>
            Steps (optional)
            <input
              name="steps"
              type="number"
              min="0"
              defaultValue={activity?.steps}
            />
          </label>
        </>
      )}
      {type !== "manual" && (
        <label>
          Duration (minutes
          {!["cycling", "treadmill"].includes(type) ? ", optional" : ""})
          <input
            name="durationMinutes"
            required={["cycling", "treadmill"].includes(type)}
            type="number"
            min="0.1"
            step="any"
            defaultValue={activity?.durationMinutes}
          />
        </label>
      )}
      {type === "treadmill" && (
        <label>
          Speed (km/h)
          <input
            name="speedKmh"
            required
            type="number"
            min="0.1"
            max="30"
            step="any"
            defaultValue={activity?.speedKmh || 5}
          />
        </label>
      )}
      {["upper_body", "pull", "push", "legs", "abs"].includes(type) && (
        <label>
          Number of exercises
          <input
            name="exerciseCount"
            required
            type="number"
            min="1"
            defaultValue={activity?.exerciseCount || 6}
          />
        </label>
      )}
      {type === "manual" && (
        <label>
          Imported/manual burn estimate (kcal)
          <input
            name="caloriesEstimate"
            required
            type="number"
            min="0"
            step="any"
            defaultValue={activity?.caloriesEstimate}
          />
        </label>
      )}
      <button className="button dark full" disabled={busy}>
        Save activity
      </button>
    </form>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
