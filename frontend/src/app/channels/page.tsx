"use client";
import { useState } from "react";
import { PageHeader, PageContent } from "@/components/layout/AppShell";
import { Card, CardHeader, Icon, ICONS, Modal, Input, CodeBlock } from "@/components/ui";
import { clsx } from "clsx";
import type { ChannelType } from "@/types";
import { useWorkspace } from "@/hooks";

interface ChannelMeta {
  type: ChannelType;
  name: string;
  icon: string;
  color: string;
  connected: boolean;
  description: string;
  webhookSuffix: string;
  setupSteps: string[];
  envVars: string[];
}

const CHANNELS: ChannelMeta[] = [
  {
    type: "telegram", name: "Telegram", icon: "🤖", color: "#229ED9",
    connected: true, description: "Send tasks via @your_bot. Supports slash commands.",
    webhookSuffix: "telegram",
    setupSteps: [
      "1. Talk to @BotFather on Telegram → /newbot",
      "2. Copy the bot token",
      "3. Set TELEGRAM_BOT_TOKEN in Render env vars",
      "4. Run the webhook registration command below",
      "5. Test: send /help to your bot",
    ],
    envVars: ["TELEGRAM_BOT_TOKEN"],
  },
  {
    type: "whatsapp", name: "WhatsApp", icon: "💬", color: "#25D366",
    connected: false, description: "Receive tasks via WhatsApp Business API.",
    webhookSuffix: "whatsapp",
    setupSteps: [
      "1. Create Meta Developer account → Add App",
      "2. Enable WhatsApp product → Get phone number",
      "3. Copy Access Token and Phone Number ID",
      "4. Set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID",
      "5. Configure webhook URL in Meta Developer Console",
      "6. Set verify token: goatraw-verify",
    ],
    envVars: ["WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"],
  },
  {
    type: "slack", name: "Slack", icon: "🟦", color: "#4A154B",
    connected: false, description: "Use @goatraw in any channel or DM.",
    webhookSuffix: "slack",
    setupSteps: [
      "1. Go to api.slack.com/apps → Create New App",
      "2. Enable Event Subscriptions → subscribe to message.channels",
      "3. Set Request URL to your webhook endpoint",
      "4. Copy Bot User OAuth Token",
      "5. Set SLACK_BOT_TOKEN in env vars",
    ],
    envVars: ["SLACK_BOT_TOKEN"],
  },
  {
    type: "discord", name: "Discord", icon: "🎮", color: "#5865F2",
    connected: false, description: "Use GoatRaw bot in your Discord server.",
    webhookSuffix: "discord",
    setupSteps: [
      "1. Go to discord.com/developers/applications → New Application",
      "2. Add Bot → copy token",
      "3. Set DISCORD_BOT_TOKEN in env vars",
      "4. Invite bot to server with message permissions",
    ],
    envVars: ["DISCORD_BOT_TOKEN"],
  },
  {
    type: "webhook", name: "Generic Webhook", icon: "🔗", color: "#7c6af7",
    connected: true, description: "POST JSON to your workspace webhook URL from any system.",
    webhookSuffix: "webhook",
    setupSteps: [
      "No setup needed — endpoint is auto-generated.",
      "POST { goal, context } to the URL below.",
      "Response: { task_id, status, poll_url }",
    ],
    envVars: [],
  },
];

const COMMANDS = [
  { cmd: "/run [goal]",   desc: "Queue an agent task" },
  { cmd: "/status",       desc: "Show recent task statuses" },
  { cmd: "/memory",       desc: "Show memory context" },
  { cmd: "/skills",       desc: "List available skills" },
  { cmd: "/help",         desc: "Show all commands" },
];

export default function ChannelsPage() {
  const { workspace } = useWorkspace();
  const [selected, setSelected] = useState<ChannelMeta | null>(null);
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "https://goatraw-api.onrender.com";
  const wsId = workspace?.id ?? "{workspace_id}";

  return (
    <>
      <PageHeader
        title="Channels"
        subtitle="Receive tasks from Telegram, WhatsApp, Slack, Discord, and webhooks"
      />
      <PageContent>
        <div className="grid grid-cols-2 gap-4 mb-6">
          {CHANNELS.map((ch) => (
            <button
              key={ch.type}
              className={clsx(
                "card-hover text-left flex items-start gap-3 cursor-pointer transition-all",
                selected?.type === ch.type && "border-accent/50 bg-surface2"
              )}
              onClick={() => setSelected(selected?.type === ch.type ? null : ch)}
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
                style={{ background: ch.color + "22" }}
              >
                {ch.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[13.5px] font-semibold">{ch.name}</span>
                  {ch.connected ? (
                    <span className="badge badge-green text-[9px]">connected</span>
                  ) : (
                    <span className="badge text-[9px]">not connected</span>
                  )}
                </div>
                <p className="text-xs text-muted">{ch.description}</p>
              </div>
              <Icon d={ICONS.chevronRight.d} size={14} className="text-muted mt-1 flex-shrink-0" />
            </button>
          ))}
        </div>

        {/* Expanded channel setup */}
        {selected && (
          <Card className="mb-6 border-accent/20 animate-fade-in">
            <CardHeader
              title={`Setup: ${selected.name}`}
              subtitle="Follow these steps to connect"
              action={
                <button className="btn btn-ghost p-1.5" onClick={() => setSelected(null)}>
                  <Icon d={ICONS.x.d} size={14} />
                </button>
              }
            />

            {/* Webhook URL */}
            <div className="mb-4">
              <label className="text-xs font-medium text-text2 block mb-1.5">Your Webhook URL</label>
              <div className="flex gap-2 items-center">
                <code className="flex-1 input font-mono text-accent2 text-xs truncate">
                  {apiBase}/webhook/{selected.webhookSuffix}/{wsId}
                </code>
                <button
                  className="btn btn-secondary text-xs"
                  onClick={() => navigator.clipboard.writeText(`${apiBase}/webhook/${selected.webhookSuffix}/${wsId}`)}
                >
                  <Icon d={ICONS.copy.d} size={12} /> Copy
                </button>
              </div>
            </div>

            {/* Setup steps */}
            <div className="mb-4">
              <label className="section-label mb-2 block">Setup Steps</label>
              <div className="space-y-1.5">
                {selected.setupSteps.map((step, i) => (
                  <div key={i} className="flex gap-2.5 text-sm">
                    <span className="font-mono text-accent2 text-xs mt-0.5 flex-shrink-0">{String(i + 1).padStart(2, "0")}</span>
                    <span className="text-text2">{step}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Telegram register command */}
            {selected.type === "telegram" && (
              <div className="mb-4">
                <label className="section-label mb-2 block">Register Webhook Command</label>
                <CodeBlock
                  language="bash"
                  code={`curl "https://api.telegram.org/bot\${TELEGRAM_BOT_TOKEN}/setWebhook?url=${apiBase}/webhook/telegram/${wsId}"`}
                />
              </div>
            )}

            {/* Env vars needed */}
            {selected.envVars.length > 0 && (
              <div>
                <label className="section-label mb-2 block">Required Env Variables</label>
                <div className="flex flex-wrap gap-2">
                  {selected.envVars.map((v) => (
                    <code key={v} className="text-[11px] font-mono bg-surface2 border border-border2 rounded px-2 py-1 text-accent2">
                      {v}
                    </code>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Slash commands reference */}
        <Card>
          <CardHeader title="Slash Commands" subtitle="Available in all connected channels" />
          <div className="divide-y divide-border">
            {COMMANDS.map((c) => (
              <div key={c.cmd} className="flex items-center gap-4 py-2.5">
                <code className="font-mono text-[12px] text-accent2 min-w-[150px]">{c.cmd}</code>
                <span className="text-sm text-text2">{c.desc}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 p-3 rounded-lg bg-surface2 border border-border2">
            <p className="text-xs text-muted">
              All messages sent to connected channels are processed through the GoatRaw agent pipeline.
              Non-command messages are treated as agent goals and queued automatically.
            </p>
          </div>
        </Card>
      </PageContent>
    </>
  );
}
