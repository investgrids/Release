import type { Metadata } from "next";
import Link from "next/link";
import {
  LifeBuoy,
  MessageSquare,
  Briefcase,
  Handshake,
  Newspaper,
  Bug,
  Clock,
  Users,
  Mail,
  ArrowRight,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Contact MarketRipple — Support, Feedback & Partnerships",
  description:
    "Reach the MarketRipple team for support, feedback, business enquiries, partnerships, media requests, or bug reports.",
  openGraph: {
    title: "Contact MarketRipple — Support, Feedback & Partnerships",
    description:
      "Reach the MarketRipple team for support, feedback, business enquiries, partnerships, media requests, or bug reports.",
  },
};

// ── Contact categories ─────────────────────────────────────────────────────────

const CATEGORIES = [
  {
    icon: LifeBuoy,
    title: "Support",
    desc: "Having trouble with the platform? Our support team will help you resolve any technical issue or usage question.",
    contact: "support@marketripple.in",
    isEmail: true,
    accent: "border-sky-500/20 bg-sky-500/[0.05]",
    iconColor: "text-sky-400",
    iconBg: "bg-sky-500/15",
  },
  {
    icon: MessageSquare,
    title: "Feedback",
    desc: "Share your experience, suggest improvements, or tell us what you wish MarketRipple did differently. All feedback shapes the roadmap.",
    contact: "feedback@marketripple.in",
    isEmail: true,
    accent: "border-violet-500/20 bg-violet-500/[0.05]",
    iconColor: "text-violet-400",
    iconBg: "bg-violet-500/15",
  },
  {
    icon: Briefcase,
    title: "Business Enquiries",
    desc: "Interested in enterprise solutions, white-label intelligence feeds, or professional subscription plans for your organisation?",
    contact: "business@marketripple.in",
    isEmail: true,
    accent: "border-emerald-500/20 bg-emerald-500/[0.05]",
    iconColor: "text-emerald-400",
    iconBg: "bg-emerald-500/15",
  },
  {
    icon: Handshake,
    title: "Partnerships",
    desc: "Data providers, financial media, exchanges, fintech platforms, and financial institutions — explore partnership opportunities.",
    contact: "partnerships@marketripple.in",
    isEmail: true,
    accent: "border-amber-500/20 bg-amber-500/[0.05]",
    iconColor: "text-amber-400",
    iconBg: "bg-amber-500/15",
  },
  {
    icon: Newspaper,
    title: "Media",
    desc: "Journalists and editors seeking press coverage, data quotes, interviews, or commentary from the MarketRipple team.",
    contact: "media@marketripple.in",
    isEmail: true,
    accent: "border-rose-500/20 bg-rose-500/[0.05]",
    iconColor: "text-rose-400",
    iconBg: "bg-rose-500/15",
  },
  {
    icon: Bug,
    title: "Bug Reports",
    desc: "Found something broken? Help us fix it. Describe the issue, the steps to reproduce it, and what you expected to happen.",
    contact: "/faq#bug",
    isEmail: false,
    accent: "border-orange-500/20 bg-orange-500/[0.05]",
    iconColor: "text-orange-400",
    iconBg: "bg-orange-500/15",
  },
];

// ── Response time table ────────────────────────────────────────────────────────

const RESPONSE_TIMES = [
  {
    category: "Support Queries",
    time: "24–48 hours",
    note: "Business days only",
  },
  {
    category: "Feedback",
    time: "Within 7 days",
    note: "Acknowledged; incorporated into roadmap review",
  },
  {
    category: "Business & Partnerships",
    time: "3–5 business days",
    note: "Initial response with next steps",
  },
  {
    category: "Bug Reports (Critical)",
    time: "Within 24 hours",
    note: "Assessed and triaged on next business day",
  },
  {
    category: "Media",
    time: "Within 24 hours",
    note: "Business days; subject to spokesperson availability",
  },
];

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ContactPage() {
  return (
    <main className="min-w-0 pb-10">
      {/* Hero */}
      <div className="mb-10">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Get in Touch
        </p>
        <h1 className="mt-3 text-[28px] font-black leading-tight text-white md:text-[36px]">
          We&apos;d Love to Hear From You
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-7 text-slate-400">
          Whether you have a support question, a product idea, or a partnership
          proposal — the MarketRipple team reads every message. Choose the right
          channel below for the fastest response.
        </p>
      </div>

      {/* Contact categories grid */}
      <section aria-labelledby="contact-categories">
        <h2
          id="contact-categories"
          className="mb-4 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500"
        >
          Contact Channels
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            return (
              <div
                key={cat.title}
                className={`rounded-xl border p-5 transition-colors ${cat.accent}`}
              >
                <div
                  className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl ${cat.iconBg}`}
                >
                  <Icon className={`h-5 w-5 ${cat.iconColor}`} />
                </div>
                <h3 className="text-[15px] font-semibold text-white">
                  {cat.title}
                </h3>
                <p className="mt-1.5 text-[12px] leading-5 text-slate-400">
                  {cat.desc}
                </p>
                <div className="mt-4">
                  {cat.isEmail ? (
                    <a
                      href={`mailto:${cat.contact}`}
                      className={`inline-flex items-center gap-1.5 text-[13px] font-medium ${cat.iconColor} underline-offset-2 hover:underline`}
                    >
                      <Mail className="h-3.5 w-3.5" />
                      {cat.contact}
                    </a>
                  ) : (
                    <Link
                      href={cat.contact}
                      className={`inline-flex items-center gap-1.5 text-[13px] font-medium ${cat.iconColor} underline-offset-2 hover:underline`}
                    >
                      See FAQ for bug reports
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Feature Requests */}
      <section
        aria-labelledby="feature-requests"
        className="mt-10 rounded-xl border border-violet-500/20 bg-violet-500/[0.04] p-6"
      >
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/15">
            <MessageSquare className="h-5 w-5 text-violet-400" />
          </div>
          <div>
            <h2
              id="feature-requests"
              className="text-[16px] font-bold text-white"
            >
              Feature Requests
            </h2>
            <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
              Your ideas directly shape what MarketRipple builds next. Every feature
              request is reviewed and discussed internally. High-demand requests
              are prioritised on our public roadmap. To submit a feature request,
              write to{" "}
              <a
                href="mailto:feedback@marketripple.in?subject=Feature Request"
                className="font-medium text-violet-400 underline-offset-2 hover:underline"
              >
                feedback@marketripple.in
              </a>{" "}
              with{" "}
              <span className="rounded-md border border-white/[0.08] bg-white/[0.06] px-1.5 py-0.5 font-mono text-[12px] text-slate-300">
                Feature Request
              </span>{" "}
              in the subject line. Please include the problem you want solved and
              any thoughts on how you imagine it working.
            </p>
          </div>
        </div>
      </section>

      {/* Response Time Table */}
      <section aria-labelledby="response-times" className="mt-10">
        <div className="mb-4 flex items-center gap-2">
          <Clock className="h-4 w-4 text-slate-400" />
          <h2
            id="response-times"
            className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500"
          >
            Expected Response Times
          </h2>
        </div>
        <div className="overflow-x-auto rounded-xl border border-white/[0.08]">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                <th className="px-5 py-3 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                  Category
                </th>
                <th className="px-5 py-3 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                  Response Time
                </th>
                <th className="px-5 py-3 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                  Note
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {RESPONSE_TIMES.map((row) => (
                <tr
                  key={row.category}
                  className="transition-colors hover:bg-white/[0.02]"
                >
                  <td className="px-5 py-3.5 font-medium text-slate-200">
                    {row.category}
                  </td>
                  <td className="px-5 py-3.5 font-semibold text-emerald-400">
                    {row.time}
                  </td>
                  <td className="px-5 py-3.5 text-slate-500">{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[11px] text-slate-600">
          Business days: Monday to Friday, excluding Indian public holidays.
          Response times are targets, not guarantees.
        </p>
      </section>

      {/* Community */}
      <section aria-labelledby="community" className="mt-10">
        <div className="rounded-xl border border-white/[0.08] bg-[#080c14] p-6">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-500/15">
              <Users className="h-5 w-5 text-sky-400" />
            </div>
            <div>
              <h2
                id="community"
                className="text-[16px] font-bold text-white"
              >
                Community
              </h2>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                A community forum and Discord server for MarketRipple users are in
                active planning. These channels will allow users to share
                research, discuss event impacts, and collaborate on investment
                themes — powered by MarketRipple intelligence. Details will be
                announced via the{" "}
                <Link
                  href="/whats-new"
                  className="font-medium text-sky-400 underline-offset-2 hover:underline"
                >
                  What&apos;s New
                </Link>{" "}
                page when they launch.
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
