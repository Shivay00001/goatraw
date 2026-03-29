"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authApi } from "@/services/api";
import { useStore } from "@/store";
import { Icon, ICONS, Spinner } from "@/components/ui";

export default function RegisterPage() {
  const [name, setName]         = useState("");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const setAuth = useStore((s) => s.setAuth);
  const router  = useRouter();

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    setError(""); setLoading(true);
    try {
      const tokens = await authApi.register(email, password, name);
      setAuth(
        { id: tokens.user_id, email, full_name: name, plan: tokens.plan, workspace_id: "", api_key: tokens.api_key },
        tokens.access_token
      );
      router.push("/dashboard");
    } catch {
      setError("Registration failed. Try a different email.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 justify-center mb-10">
          <div className="w-9 h-9 rounded-xl bg-accent flex items-center justify-center text-xl">🦅</div>
          <span className="font-mono font-bold text-xl text-accent2">GoatRaw</span>
        </div>

        <div className="card border-border2">
          <h1 className="text-lg font-bold mb-1">Create account</h1>
          <p className="text-sm text-muted mb-6">Start free · No credit card required</p>

          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label className="text-xs font-medium text-text2 block mb-1.5">Full Name</label>
              <input className="input" type="text" placeholder="Sanskruti Shah"
                value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <label className="text-xs font-medium text-text2 block mb-1.5">Email</label>
              <input className="input" type="email" placeholder="you@company.com"
                value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="text-xs font-medium text-text2 block mb-1.5">Password</label>
              <input className="input" type="password" placeholder="Min 8 characters"
                value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
            </div>

            {error && (
              <div className="text-xs text-red bg-red/5 border border-red/20 rounded-lg px-3 py-2">{error}</div>
            )}

            <button type="submit" className="btn btn-primary w-full justify-center py-2.5" disabled={loading}>
              {loading ? <Spinner size={15} /> : <Icon d={ICONS.arrowRight.d} size={15} />}
              {loading ? "Creating account..." : "Create Account"}
            </button>
          </form>

          <div className="my-4 border-t border-border" />

          <div className="space-y-1.5">
            {["10 free tasks/hour", "All agent types", "Telegram + Webhook channels", "3-tier memory"].map((f) => (
              <div key={f} className="flex items-center gap-2 text-xs text-text2">
                <Icon d={ICONS.check.d} size={11} className="text-green flex-shrink-0" /> {f}
              </div>
            ))}
          </div>

          <p className="text-center text-xs text-muted mt-5">
            Already have an account?{" "}
            <Link href="/auth/login" className="text-accent2 hover:underline">Sign in →</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
