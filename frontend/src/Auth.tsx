import React, { useEffect, useState } from "react";
import { api, ApiError, setCsrf } from "./api";
export type User = {
  id: string;
  email: string;
  gender: "male" | "female";
  age: number;
  heightCm: number;
  weightKg: number;
};
export function ProfileFields({ user }: { user?: User }) {
  return (
    <div className="settings-grid">
      <label>
        Gender
        <select name="gender" required defaultValue={user?.gender || ""}>
          <option value="" disabled>
            Select male or female
          </option>
          <option value="male">Male</option>
          <option value="female">Female</option>
        </select>
      </label>
      <label>
        Age (years)
        <input
          name="age"
          type="number"
          min="18"
          max="100"
          required
          defaultValue={user?.age}
        />
      </label>
      <label>
        Weight (kg)
        <input
          name="weightKg"
          type="number"
          min="20"
          max="350"
          step="0.1"
          required
          defaultValue={user?.weightKg}
        />
      </label>
      <label>
        Height (cm)
        <input
          name="heightCm"
          type="number"
          min="100"
          max="250"
          step="0.1"
          required
          defaultValue={user?.heightCm}
        />
      </label>
    </div>
  );
}
export function profileData(f: FormData) {
  return {
    gender: f.get("gender"),
    age: Number(f.get("age")),
    weightKg: Number(f.get("weightKg")),
    heightCm: Number(f.get("heightCm")),
  };
}
export function AuthGate({
  children,
}: {
  children: (
    user: User,
    logout: () => Promise<void>,
    update: (user: User) => void,
  ) => React.ReactNode;
}) {
  const [user, setUser] = useState<User | null>(null),
    [ready, setReady] = useState(false),
    [signup, setSignup] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function restore() {
    setError("");
    setBusy(true);
    try {
      const result = await api("/auth/me");
      setCsrf(result.csrfToken);
      setUser(result.user);
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401))
        setError((e as Error).message);
    } finally {
      setReady(true);
      setBusy(false);
    }
  }
  useEffect(() => {
    restore();
    const expired = () => {
      setUser(null);
      setCsrf("");
      setError("Your session expired. Please log in again.");
    };
    window.addEventListener("fitlog-session-expired", expired);
    return () => window.removeEventListener("fitlog-session-expired", expired);
  }, []);
  async function logout() {
    setBusy(true);
    try {
      await api("/auth/logout", "POST");
      setCsrf("");
      setUser(null);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!ready)
    return (
      <div className="auth-shell">
        <p>Loading fitlog…</p>
      </div>
    );
  if (user)
    return (
      <>
        {error && (
          <div role="alert" className="auth-error">
            {error}
          </div>
        )}
        {children(user, logout, setUser)}
      </>
    );
  return (
    <main className="auth-shell">
      <section className="card auth-card">
        <div className="eyebrow">FITLOG</div>
        <h1>{signup ? "Start your daily rhythm." : "Welcome back."}</h1>
        <p className="intro">
          {signup
            ? "Personal calorie estimates, food logging, and activity in one place."
            : "Log in to your private food and activity journal."}
        </p>
        <div className="auth-tabs">
          <button
            type="button"
            className={!signup ? "button dark" : "button"}
            onClick={() => {
              setSignup(false);
              setError("");
            }}
          >
            Log in
          </button>
          <button
            type="button"
            className={signup ? "button dark" : "button"}
            onClick={() => {
              setSignup(true);
              setError("");
            }}
          >
            Sign up
          </button>
        </div>
        <form
          key={String(signup)}
          onSubmit={async (e) => {
            e.preventDefault();
            if (busy) return;
            const f = new FormData(e.currentTarget);
            setBusy(true);
            setError("");
            try {
              const result = await api(
                "/auth/" + (signup ? "signup" : "login"),
                "POST",
                {
                  email: f.get("email"),
                  password: f.get("password"),
                  ...(signup ? profileData(f) : {}),
                },
              );
              setCsrf(result.csrfToken);
              setUser(result.user);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Email
            <input
              name="email"
              type="email"
              maxLength={254}
              autoComplete="email"
              required
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              minLength={10}
              maxLength={128}
              autoComplete={signup ? "new-password" : "current-password"}
              required
            />
            {signup && <small>Use at least 10 characters.</small>}
          </label>
          {signup && (
            <>
              <ProfileFields />
              <p className="auth-note">
                Male/female selects the sex coefficient in the Mifflin–St Jeor
                equation. Age, weight, and height are also required. Estimates
                are intended for adults.
              </p>
            </>
          )}
          {error && (
            <p role="alert" className="auth-error">
              {error}
            </p>
          )}
          <button className="button dark full" disabled={busy}>
            {busy ? "Please wait…" : signup ? "Create account" : "Log in"}
          </button>
        </form>
        {error && (
          <button
            type="button"
            className="button"
            disabled={busy}
            onClick={restore}
          >
            Check existing session
          </button>
        )}
      </section>
    </main>
  );
}
