"use client";
import { useState } from "react";
import { PageHeader, PageContent } from "@/components/layout/AppShell";
import { Card, Icon, ICONS, Spinner } from "@/components/ui";
import { useUser } from "@/store";
import { clsx } from "clsx";

declare global {
  interface Window { Razorpay: new (opts: object) => { open(): void }; }
}

const PLANS = [
  {
    key:   "free",
    name:  "Free",
    price: "₹0",
    per:   "forever",
    color: "border-border",
    badge: "",
    features: [
      "10 tasks / hour",
      "100 tasks / month",
      "50 memory facts",
      "2 cron jobs",
      "1 channel (Webhook)",
      "5 skills",
      "General agent",
    ],
    missing: ["Heartbeat daemon", "Lead Gen agent", "Competitor analysis", "CSV export", "API key access"],
  },
  {
    key:   "pro",
    name:  "Pro",
    price: "₹2,999",
    per:   "/ month",
    color: "border-accent/50 ring-2 ring-accent/20",
    badge: "Most Popular",
    features: [
      "100 tasks / hour",
      "2,000 tasks / month",
      "500 memory facts",
      "20 cron jobs",
      "5 channels (Telegram + WhatsApp + Slack + Discord)",
      "50 skills + AI generation",
      "All specialized agents",
      "Heartbeat daemon",
      "CSV + JSON export",
      "API key access",
      "Priority support",
    ],
    missing: [],
  },
  {
    key:   "enterprise",
    name:  "Enterprise",
    price: "₹14,999",
    per:   "/ month",
    color: "border-yellow/40",
    badge: "",
    features: [
      "1,000 tasks / hour",
      "Unlimited tasks",
      "Unlimited memory",
      "Unlimited cron jobs",
      "All channels + custom webhook",
      "Unlimited skills",
      "White-label option",
      "Dedicated Slack support",
      "Custom agent development",
      "Invoice billing",
      "SLA guarantee",
    ],
    missing: [],
  },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function UpgradePage() {
  const user     = useUser();
  const [loading, setLoading] = useState<string | null>(null);
  const currentPlan = user?.plan ?? "free";

  const handleUpgrade = async (planKey: string) => {
    if (planKey === "free" || planKey === currentPlan) return;

    setLoading(planKey);
    try {
      // 1. Create subscription via backend
      const res = await fetch(`${API_BASE}/payments/subscribe`, {
        method:  "POST",
        headers: {
          "Authorization":  `Bearer ${localStorage.getItem("gr_token")}`,
          "Content-Type":   "application/json",
        },
        body: JSON.stringify({ plan: planKey }),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail ?? "Subscription failed");

      // 2. Load Razorpay script if not already loaded
      if (!window.Razorpay) {
        await new Promise<void>((resolve, reject) => {
          const script  = document.createElement("script");
          script.src    = "https://checkout.razorpay.com/v1/checkout.js";
          script.onload = () => resolve();
          script.onerror= () => reject(new Error("Failed to load Razorpay"));
          document.body.appendChild(script);
        });
      }

      // 3. Open Razorpay checkout
      const rzp = new window.Razorpay({
        key:             data.razorpay_key_id,
        subscription_id: data.subscription_id,
        name:            "GoatRaw",
        description:     `GoatRaw ${planKey.charAt(0).toUpperCase() + planKey.slice(1)} Plan`,
        image:           "/logo.png",
        prefill:         data.prefill,
        notes:           data.notes,
        theme:           { color: "#7c6af7" },
        handler: async (response: { razorpay_payment_id: string; razorpay_subscription_id: string; razorpay_signature: string }) => {
          // 4. Verify payment
          const verifyRes = await fetch(`${API_BASE}/payments/verify-payment`, {
            method:  "POST",
            headers: {
              "Authorization": `Bearer ${localStorage.getItem("gr_token")}`,
              "Content-Type":  "application/json",
            },
            body: JSON.stringify({
              razorpay_payment_id:      response.razorpay_payment_id,
              razorpay_subscription_id: response.razorpay_subscription_id,
              razorpay_signature:       response.razorpay_signature,
              plan:                     planKey,
            }),
          });
          const verifyData = await verifyRes.json();
          if (verifyRes.ok) {
            alert(`🎉 Welcome to GoatRaw ${planKey.charAt(0).toUpperCase() + planKey.slice(1)}! Refresh to see your updated plan.`);
            window.location.reload();
          }
        },
      });
      rzp.open();
    } catch (e: unknown) {
      alert((e as Error).message ?? "Upgrade failed. Please try again.");
    } finally {
      setLoading(null);
    }
  };

  return (
    <>
      <PageHeader title="Upgrade Plan" subtitle="Unlock the full power of GoatRaw" />
      <PageContent>
        {/* Current plan banner */}
        {currentPlan !== "free" && (
          <div className="mb-6 p-3 rounded-xl border border-accent/30 bg-accent/5 flex items-center gap-3">
            <span className="text-accent2 font-mono text-sm font-bold">
              Current: {currentPlan.toUpperCase()}
            </span>
            <span className="text-xs text-muted">Your subscription is active.</span>
          </div>
        )}

        <div className="grid grid-cols-3 gap-5">
          {PLANS.map((plan) => {
            const isCurrentPlan = plan.key === currentPlan;
            const canUpgrade    = plan.key !== "free" && !isCurrentPlan;

            return (
              <div key={plan.key}
                className={clsx(
                  "card relative flex flex-col transition-all duration-200",
                  plan.color,
                  isCurrentPlan && "opacity-80"
                )}>
                {plan.badge && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 badge bg-accent text-white border-accent text-[10px] px-3 py-1">
                    {plan.badge}
                  </div>
                )}

                <div className="mb-5">
                  <div className="text-[11px] font-mono text-muted mb-1 uppercase tracking-widest">{plan.name}</div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold font-mono text-text">{plan.price}</span>
                    <span className="text-xs text-muted">{plan.per}</span>
                  </div>
                </div>

                <ul className="flex-1 space-y-2 mb-6">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-xs text-text2">
                      <Icon d={ICONS.check.d} size={11} className="text-green flex-shrink-0 mt-0.5" />
                      {f}
                    </li>
                  ))}
                  {plan.missing.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-xs text-muted line-through">
                      <Icon d={ICONS.x.d} size={11} className="text-muted flex-shrink-0 mt-0.5" />
                      {f}
                    </li>
                  ))}
                </ul>

                <button
                  className={clsx(
                    "btn w-full justify-center py-2.5",
                    isCurrentPlan ? "btn-ghost cursor-default opacity-60"
                    : canUpgrade  ? "btn-primary"
                    : "btn-ghost"
                  )}
                  onClick={() => handleUpgrade(plan.key)}
                  disabled={!canUpgrade || loading === plan.key}
                >
                  {loading === plan.key ? (
                    <Spinner size={14} />
                  ) : isCurrentPlan ? (
                    "Current Plan"
                  ) : plan.key === "free" ? (
                    "Downgrade"
                  ) : (
                    <>
                      <Icon d={ICONS.zap.d} size={14} />
                      Upgrade to {plan.name}
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        {/* FAQ */}
        <Card className="mt-8">
          <div className="section-label mb-4">Common Questions</div>
          <div className="space-y-4">
            {[
              ["Can I cancel anytime?", "Yes. Cancel your Razorpay subscription anytime from the settings page. Your plan stays active until end of billing period."],
              ["What payment methods are supported?", "UPI, credit/debit cards, net banking, wallets — everything Razorpay supports."],
              ["Can I get an invoice?", "Yes — Razorpay sends a GST invoice automatically. Enterprise plan includes custom invoicing."],
              ["What happens if I exceed my task limit?", "Requests return a 429 error. Upgrade your plan or wait for the hourly reset."],
              ["Is there a free trial for Pro?", "Contact us for a 7-day Pro trial. Email: trial@goatraw.ai"],
            ].map(([q, a]) => (
              <div key={q}>
                <div className="text-[13px] font-semibold mb-1">{q}</div>
                <div className="text-xs text-muted">{a}</div>
              </div>
            ))}
          </div>
        </Card>
      </PageContent>
    </>
  );
}
