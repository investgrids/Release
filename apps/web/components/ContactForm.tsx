"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Send, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

const CATEGORIES = [
  { value: "general",     label: "General Query" },
  { value: "support",     label: "Support" },
  { value: "feedback",    label: "Feedback" },
  { value: "business",    label: "Business Enquiry" },
  { value: "partnership", label: "Partnership" },
  { value: "media",       label: "Media" },
  { value: "bug",         label: "Bug Report" },
  { value: "pro_interest",label: "Interested in Pro" },
];

type Status = "idle" | "submitting" | "success" | "error";

export function ContactForm() {
  const searchParams = useSearchParams();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [category, setCategory] = useState("general");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const topic = searchParams.get("topic");
    if (topic === "pro") setCategory("pro_interest");
  }, [searchParams]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("submitting");
    setError(null);
    try {
      const res = await fetch(`${API}/api/feedback/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim() || null,
          email: email.trim(),
          category,
          message: message.trim(),
          page_url: typeof window !== "undefined" ? window.location.pathname : null,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const detail = data?.detail;
        const msg = Array.isArray(detail)
          ? detail.map((d: any) => d.msg).join(" ")
          : (typeof detail === "string" ? detail : "Something went wrong. Please try again.");
        setError(msg);
        setStatus("error");
        return;
      }
      setStatus("success");
      setName(""); setEmail(""); setMessage(""); setCategory("general");
    } catch {
      setError("Could not reach the server. Please check your connection and try again.");
      setStatus("error");
    }
  }

  if (status === "success") {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.05] p-8 text-center">
        <CheckCircle2 className="h-8 w-8 text-emerald-400" />
        <p className="text-[15px] font-semibold text-white">Message sent</p>
        <p className="text-[13px] text-slate-400">
          Thanks for reaching out — our team reads every message and will get back to you at the email you provided.
        </p>
        <button
          onClick={() => setStatus("idle")}
          className="mt-2 text-[12px] font-medium text-sky-400 hover:text-sky-300 transition"
        >
          Send another message
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-white/[0.08] bg-white/[0.02] p-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="cf-name" className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Name <span className="text-slate-700">(optional)</span>
          </label>
          <input
            id="cf-name"
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            maxLength={128}
            className="w-full rounded-lg border border-white/10 bg-[#0a0d16] px-3 py-2.5 text-[13px] text-white outline-none transition focus:border-sky-500/50"
            placeholder="Your name"
          />
        </div>
        <div>
          <label htmlFor="cf-email" className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Email <span className="text-rose-500">*</span>
          </label>
          <input
            id="cf-email"
            type="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-[#0a0d16] px-3 py-2.5 text-[13px] text-white outline-none transition focus:border-sky-500/50"
            placeholder="you@example.com"
          />
        </div>
      </div>

      <div>
        <label htmlFor="cf-category" className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Category
        </label>
        <select
          id="cf-category"
          value={category}
          onChange={e => setCategory(e.target.value)}
          className="w-full cursor-pointer rounded-lg border border-white/10 bg-[#0a0d16] px-3 py-2.5 text-[13px] text-white outline-none transition focus:border-sky-500/50"
        >
          {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>

      <div>
        <label htmlFor="cf-message" className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Message <span className="text-rose-500">*</span>
        </label>
        <textarea
          id="cf-message"
          required
          minLength={10}
          maxLength={5000}
          rows={5}
          value={message}
          onChange={e => setMessage(e.target.value)}
          className="w-full resize-y rounded-lg border border-white/10 bg-[#0a0d16] px-3 py-2.5 text-[13px] text-white outline-none transition focus:border-sky-500/50"
          placeholder="Tell us what's on your mind — a question, feedback, or a bug you ran into."
        />
      </div>

      {status === "error" && error && (
        <div className="flex items-start gap-2 rounded-lg border border-rose-500/20 bg-rose-500/[0.06] px-3 py-2.5">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-400" />
          <p className="text-[12px] text-rose-300">{error}</p>
        </div>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-sky-500 py-3 text-[13px] font-bold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {status === "submitting" ? (
          <><Loader2 className="h-4 w-4 animate-spin" /> Sending…</>
        ) : (
          <><Send className="h-3.5 w-3.5" /> Send Message</>
        )}
      </button>
    </form>
  );
}
