"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authApi } from "@/services/api";
import { useStore } from "@/store";
import { Icon, ICONS, Spinner } from "@/components/ui";

export default function LoginPage() {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const setAuth = useStore((s) => s.setAuth);
  const router  = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const tokens = await authApi.login(email, password);
      setAuth(
        { id: tokens.user_id, email, full_name: "", plan: tokens.plan, workspace_id: "", api_key: tokens.api_key },
        tokens.access_token
      );
      router.push("/dashboard");
    } catch {
      setError("Invalid email or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-2.5 justify-center mb-10">
          <div className="w-9 h-9 rounded-xl bg-accent flex items-center justify-center text-xl">🦅</div>
          <span className="font-mono font-bold text-xl text-accent2">GoatRaw</span>
        </div>

        <div className="card border-border2">
          <h1 className="text-lg font-bold mb-1">Welcome back</h1>
          <p className="text-sm text-muted mb-6">Sign in to your agent platform</p>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="text-xs font-medium text-text2 block mb-1.5">Email</label>
              <input className="input" type="email" placeholder="you@company.com"
                value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="text-xs font-medium text-text2 block mb-1.5">Password</label>
              <input className="input" type="password" placeholder="••••••••"
                value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>

            {error && (
              <div className="text-xs text-red bg-red/5 border border-red/20 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary w-full justify-center py-2.5" disabled={loading}>
              {loading ? <Spinner size={15} /> : <Icon d={ICONS.arrowRight.d} size={15} />}
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>

          <p className="text-center text-xs text-muted mt-5">
            No account?{" "}
            <Link href="/auth/register" className="text-accent2 hover:underline">Create one →</Link>
          </p>
        </div>

        <p className="text-center text-[11px] text-muted mt-6">
          GoatRaw v2 · Autonomous AI Agent Platform
        </p>
      </div>
    </div>
  );
}
