import type { Metadata } from "next";
import Link from "next/link";
import {
  ShieldCheck,
  FileText,
  TriangleAlert,
  TrendingDown,
  Cookie,
  ChevronRight,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Legal — Privacy Policy, Terms of Service & Disclaimer | MarketRipple",
  description:
    "Read MarketRipple's Privacy Policy, Terms of Service, AI Disclaimer, Risk Disclosure, and Cookie Information. Platform governed under Indian law.",
  openGraph: {
    title: "Legal — Privacy Policy, Terms of Service & Disclaimer | MarketRipple",
    description:
      "Privacy Policy, Terms of Service, AI Disclaimer, Risk Disclosure, and Cookie Information for MarketRipple — AI-powered Indian market intelligence.",
  },
};

// ── Section navigation ─────────────────────────────────────────────────────────

const SECTIONS = [
  { id: "privacy",    label: "Privacy Policy",    icon: ShieldCheck  },
  { id: "terms",      label: "Terms of Service",  icon: FileText     },
  { id: "disclaimer", label: "Disclaimer",        icon: TriangleAlert },
  { id: "risk",       label: "Risk Disclosure",   icon: TrendingDown },
  { id: "cookies",    label: "Cookie Information",icon: Cookie       },
];

// ── Helper: section heading ────────────────────────────────────────────────────

function SectionHeading({
  id,
  icon: Icon,
  title,
  color = "text-slate-300",
  bg = "bg-white/[0.06]",
}: {
  id: string;
  icon: typeof ShieldCheck;
  title: string;
  color?: string;
  bg?: string;
}) {
  return (
    <div id={id} className="flex scroll-mt-20 items-center gap-3 border-b border-white/[0.06] pb-4">
      <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${bg}`}>
        <Icon className={`h-4.5 w-4.5 ${color}`} />
      </div>
      <h2 className="text-[20px] font-bold text-white">{title}</h2>
    </div>
  );
}

// ── Helper: list ──────────────────────────────────────────────────────────────

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="mt-3 space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2.5">
          <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-600" />
          <span className="text-[13px] leading-6 text-slate-400">{item}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Helper: subsection ─────────────────────────────────────────────────────────

function Sub({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <h3 className="text-[14px] font-semibold text-slate-200">{title}</h3>
      {children}
    </div>
  );
}

// ── Disclaimer callout ─────────────────────────────────────────────────────────

function DisclaimerCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/[0.06] p-5">
      <div className="flex items-start gap-3">
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
        <div className="text-[13px] leading-6 text-amber-200/80">{children}</div>
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function LegalPage() {
  return (
    <main className="min-w-0 pb-10">
      {/* Page header */}
      <div className="mb-8">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Legal Information
        </p>
        <h1 className="mt-3 text-[28px] font-black leading-tight text-white md:text-[36px]">
          Legal & Compliance
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-7 text-slate-400">
          MarketRipple is operated and governed under Indian law. Please read these
          documents carefully before using the platform. Last updated:{" "}
          <span className="font-medium text-slate-300">July 2025</span>.
        </p>

        {/* Section nav */}
        <nav
          aria-label="Legal sections"
          className="mt-6 flex flex-wrap gap-2"
        >
          {SECTIONS.map((s) => {
            const Icon = s.icon;
            return (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-[12px] text-slate-400 transition hover:border-white/[0.14] hover:text-slate-200"
              >
                <Icon className="h-3.5 w-3.5" />
                {s.label}
              </a>
            );
          })}
        </nav>
      </div>

      {/* Content */}
      <div className="space-y-10">

        {/* ── Privacy Policy ─────────────────────────────────────────────────── */}
        <section
          aria-labelledby="privacy"
          className="rounded-xl border border-white/[0.08] bg-[#080c14] p-6"
        >
          <SectionHeading
            id="privacy"
            icon={ShieldCheck}
            title="Privacy Policy"
            color="text-sky-400"
            bg="bg-sky-500/15"
          />

          <p className="mt-4 text-[13px] leading-6 text-slate-400">
            MarketRipple is committed to protecting the privacy of its users. Because
            the platform currently operates without user accounts, the personal
            data we collect is minimal.
          </p>

          <Sub title="Information We Collect">
            <BulletList
              items={[
                "No personal accounts: MarketRipple does not require registration, login, or the submission of any personal details such as name, email address, or phone number.",
                "Anonymous usage analytics: We collect aggregated, anonymised data about which pages are visited, which features are used most, and general traffic patterns. This data cannot be linked to any individual.",
                "No personal behavioural cookies: We do not deploy cookies that track individual browsing behaviour across websites or build personal profiles.",
              ]}
            />
          </Sub>

          <Sub title="How We Use Information">
            <BulletList
              items={[
                "To understand how the platform is being used so that we can prioritise improvements and new features.",
                "To monitor platform performance, identify technical issues, and maintain reliability.",
                "To analyse aggregate demand for different platform sections and AI features.",
              ]}
            />
          </Sub>

          <Sub title="Third-Party Services">
            <BulletList
              items={[
                "Market data is sourced from providers including yfinance and financial data APIs. These providers have their own data policies, which you can review on their respective websites.",
                "AI analysis is powered by models accessed through OpenRouter (currently free-tier models). OpenRouter's privacy policy governs how query data is handled on their infrastructure.",
                "We do not sell, share, or transfer any user data to third parties for advertising or marketing purposes.",
              ]}
            />
          </Sub>

          <Sub title="Data Security">
            <p className="mt-2 text-[13px] leading-6 text-slate-400">
              Because MarketRipple does not collect personal identifying information,
              there is no personal data at risk in the event of a security
              incident. Anonymous analytics data is held on secured
              infrastructure with access limited to the MarketRipple development
              team.
            </p>
          </Sub>

          <Sub title="Changes to This Policy">
            <p className="mt-2 text-[13px] leading-6 text-slate-400">
              Any material changes to this Privacy Policy will be announced via
              the{" "}
              <Link
                href="/whats-new"
                className="text-sky-400 underline-offset-2 hover:underline"
              >
                What&apos;s New
              </Link>{" "}
              page with at least 14 days&apos; notice before taking effect. The
              updated policy will carry a revised &quot;Last Updated&quot; date at the top
              of this page.
            </p>
          </Sub>
        </section>

        {/* ── Terms of Service ───────────────────────────────────────────────── */}
        <section
          aria-labelledby="terms"
          className="rounded-xl border border-white/[0.08] bg-[#080c14] p-6"
        >
          <SectionHeading
            id="terms"
            icon={FileText}
            title="Terms of Service"
            color="text-violet-400"
            bg="bg-violet-500/15"
          />

          <p className="mt-4 text-[13px] leading-6 text-slate-400">
            By accessing and using MarketRipple, you agree to be bound by these Terms
            of Service. If you do not agree, please discontinue use of the
            platform immediately.
          </p>

          <Sub title="1. Acceptance of Terms">
            <p className="mt-2 text-[13px] leading-6 text-slate-400">
              Use of the MarketRipple platform constitutes acceptance of these terms
              and all policies incorporated by reference, including the Privacy
              Policy and Disclaimer. These terms may be updated periodically.
              Continued use after any update constitutes acceptance of the
              revised terms.
            </p>
          </Sub>

          <Sub title="2. Permitted Use">
            <BulletList
              items={[
                "MarketRipple is made available for personal, non-commercial research and information purposes only.",
                "You may use the platform to research market events, understand sector impacts, and support your personal investment decision-making process.",
                "Use of the platform by financial professionals for internal research is permitted, subject to the prohibited uses listed below.",
              ]}
            />
          </Sub>

          <Sub title="3. Intellectual Property">
            <BulletList
              items={[
                "All content generated by MarketRipple — including AI analysis, event classifications, ripple cascade graphs, opportunity scores, and Stories — is the intellectual property of MarketRipple and its operators.",
                "Raw market data and news content are owned by their respective providers and are governed by their own terms and licences.",
                "You may not reproduce, republish, or commercially distribute MarketRipple's AI-generated content without prior written permission.",
              ]}
            />
          </Sub>

          <Sub title="4. Prohibited Uses">
            <BulletList
              items={[
                "Automated scraping, crawling, or systematic extraction of MarketRipple's content, data, or AI outputs is strictly prohibited.",
                "Redistribution of MarketRipple's AI analysis, event data, or opportunity scores — whether commercially or non-commercially — without written permission is not permitted.",
                "Use of MarketRipple's data or AI outputs as inputs to commercial algorithmic trading systems without an appropriate data licence agreement is prohibited.",
                "Any use of the platform that violates applicable Indian law, including the Information Technology Act 2000 and Securities and Exchange Board of India (SEBI) regulations, is strictly prohibited.",
              ]}
            />
          </Sub>

          <Sub title="5. Limitation of Liability">
            <p className="mt-2 text-[13px] leading-6 text-slate-400">
              To the fullest extent permitted by applicable law, MarketRipple and its
              operators shall not be liable for any direct, indirect, incidental,
              consequential, or special damages arising from your use of the
              platform or reliance on any information provided therein. This
              includes, without limitation, losses arising from investment
              decisions made on the basis of MarketRipple content.
            </p>
          </Sub>

          <Sub title="6. Changes to the Service">
            <p className="mt-2 text-[13px] leading-6 text-slate-400">
              MarketRipple reserves the right to modify, suspend, or discontinue any
              part of the platform at any time, with or without notice. We will
              make reasonable efforts to announce significant changes via the
              What&apos;s New page in advance.
            </p>
          </Sub>
        </section>

        {/* ── Disclaimer ─────────────────────────────────────────────────────── */}
        <section
          aria-labelledby="disclaimer"
          className="rounded-xl border border-white/[0.08] bg-[#080c14] p-6"
        >
          <SectionHeading
            id="disclaimer"
            icon={TriangleAlert}
            title="Disclaimer"
            color="text-amber-400"
            bg="bg-amber-500/15"
          />

          <DisclaimerCallout>
            <strong className="block mb-1 text-amber-300">
              Important: Please read this section carefully before using any
              information from MarketRipple for any investment purpose.
            </strong>
            MarketRipple is a market research and intelligence tool, not a
            registered investment advisor, stockbroker, or financial planning
            service. Nothing on this platform constitutes investment advice.
          </DisclaimerCallout>

          <div className="mt-5 space-y-4">
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-[13px] font-semibold text-slate-200">
                Research Tool Only
              </h3>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                MarketRipple provides market intelligence, event analysis, and
                AI-generated insights for research and educational purposes
                only. The platform is designed to help users understand market
                events and their potential effects — it is not designed to
                provide personalised financial advice.
              </p>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-[13px] font-semibold text-slate-200">
                Not a Registered Financial Entity
              </h3>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                MarketRipple is NOT registered with the Securities and Exchange
                Board of India (SEBI) as an Investment Adviser, Research
                Analyst, Stock Broker, Portfolio Manager, or in any other
                regulated financial capacity. No content on MarketRipple should be
                construed as a recommendation to buy, sell, or hold any
                security.
              </p>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-[13px] font-semibold text-slate-200">
                AI-Generated Analysis
              </h3>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                AI analysis, confidence scores, impact ratings, and opportunity
                scores on MarketRipple are generated by automated models based on
                publicly available information. These outputs may contain
                errors, omissions, or outdated information. They reflect the
                model&apos;s probability estimates at the time of generation and do
                not constitute facts or guaranteed outcomes.
              </p>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-[13px] font-semibold text-slate-200">
                Past Performance
              </h3>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                Any historical market data, past performance information, or
                backtested analysis shown on MarketRipple does not guarantee or
                predict future results. Markets can and do behave differently
                from historical patterns, particularly during periods of unusual
                economic stress.
              </p>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-[13px] font-semibold text-slate-200">
                Data Delays
              </h3>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                Market data on MarketRipple is subject to delays (typically 15
                minutes for equity prices). This data must not be used for
                real-time trading decisions. Always use a live, regulated
                trading platform with real-time data feeds for execution
                decisions.
              </p>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-[13px] font-semibold text-slate-200">
                User Responsibility
              </h3>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                All investment decisions are solely the responsibility of the
                user. MarketRipple expressly disclaims any liability for investment
                losses arising from reliance on content published on the
                platform. Users are strongly advised to consult a SEBI-registered
                investment adviser for personalised investment guidance tailored
                to their financial situation, goals, and risk tolerance.
              </p>
            </div>
          </div>
        </section>

        {/* ── Risk Disclosure ────────────────────────────────────────────────── */}
        <section
          aria-labelledby="risk"
          className="rounded-xl border border-white/[0.08] bg-[#080c14] p-6"
        >
          <SectionHeading
            id="risk"
            icon={TrendingDown}
            title="Risk Disclosure"
            color="text-rose-400"
            bg="bg-rose-500/15"
          />

          <p className="mt-4 text-[13px] leading-6 text-slate-400">
            Investment in securities markets involves substantial risk. The
            following disclosures are provided to help users understand the
            risks associated with equity investing in Indian markets.
          </p>

          <Sub title="General Market Risk">
            <BulletList
              items={[
                "The prices of securities listed on the BSE and NSE can fall as well as rise. There is no guarantee that the value of any investment will increase over time.",
                "Past performance of any security, index, or sector is not indicative of, nor a guarantee of, future results.",
                "Market returns can be volatile and may be significantly affected by events that are difficult or impossible to predict.",
              ]}
            />
          </Sub>

          <Sub title="Specific Risk Factors">
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {[
                {
                  risk: "Equity Risk",
                  desc: "Stock prices fluctuate based on company performance, market sentiment, sector trends, and macroeconomic conditions. Losses may be significant.",
                },
                {
                  risk: "Liquidity Risk",
                  desc: "Some securities, particularly in the small-cap and micro-cap segments, may have limited trading volumes, making it difficult to exit positions without significantly affecting price.",
                },
                {
                  risk: "Volatility Risk",
                  desc: "Indian markets can experience sharp, rapid price movements. High-impact events — budget announcements, RBI decisions, global shocks — can cause sudden, large price swings.",
                },
                {
                  risk: "Geopolitical Risk",
                  desc: "Geopolitical tensions, border conflicts, trade disputes, and diplomatic developments can negatively affect market sentiment and specific sectors.",
                },
                {
                  risk: "Currency Risk",
                  desc: "For investments in foreign-listed securities or companies with significant foreign-currency revenues or debt, exchange rate movements add an additional layer of risk.",
                },
                {
                  risk: "Regulatory Risk",
                  desc: "Changes in SEBI regulations, RBI policy, sector-specific regulatory frameworks, or taxation rules can materially affect the value of investments in affected sectors.",
                },
              ].map((item) => (
                <div
                  key={item.risk}
                  className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4"
                >
                  <h4 className="text-[13px] font-semibold text-rose-300">
                    {item.risk}
                  </h4>
                  <p className="mt-1.5 text-[12px] leading-5 text-slate-400">
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </Sub>

          <Sub title="Small-Cap and Mid-Cap Risk">
            <p className="mt-2 text-[13px] leading-6 text-slate-400">
              Small-cap and mid-cap stocks carry materially higher risk than
              large-cap securities. They are more susceptible to liquidity
              squeezes, have lower analyst coverage, and can experience more
              severe drawdowns during broad market corrections. MarketRipple covers
              companies across all market capitalisations — exercise additional
              caution when researching smaller companies.
            </p>
          </Sub>

          <Sub title="Derivatives and Options">
            <p className="mt-2 text-[13px] leading-6 text-slate-400">
              Options, futures, and other derivative instruments involve risks
              beyond those associated with direct equity investment, including
              leverage risk, time decay, counterparty risk, and the potential
              to lose the entire premium paid. Derivatives are complex
              instruments and are suitable only for experienced investors who
              fully understand the risks involved.
            </p>
          </Sub>
        </section>

        {/* ── Cookie Information ─────────────────────────────────────────────── */}
        <section
          aria-labelledby="cookies"
          className="rounded-xl border border-white/[0.08] bg-[#080c14] p-6"
        >
          <SectionHeading
            id="cookies"
            icon={Cookie}
            title="Cookie Information"
            color="text-emerald-400"
            bg="bg-emerald-500/15"
          />

          <p className="mt-4 text-[13px] leading-6 text-slate-400">
            MarketRipple uses cookies sparingly and only where necessary for the
            platform to function correctly. We do not use cookies for
            advertising, tracking, or building personal profiles.
          </p>

          <div className="mt-5 space-y-3">
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/[0.04] p-4">
              <h3 className="text-[13px] font-semibold text-emerald-300">
                Essential Session Cookies Only
              </h3>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                MarketRipple uses only essential cookies required for basic session
                management and platform functionality. These cookies are
                necessary for the platform to operate correctly and cannot be
                disabled without affecting core features.
              </p>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-[13px] font-semibold text-slate-200">
                No Advertising or Tracking Cookies
              </h3>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                MarketRipple does not deploy third-party advertising cookies,
                retargeting pixels, social media tracking cookies, or any other
                cookies designed to monitor your behaviour across other websites
                or build a personal advertising profile.
              </p>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-[13px] font-semibold text-slate-200">
                Clearing Your Cookies
              </h3>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                You may clear cookies stored by MarketRipple at any time through
                your browser&apos;s privacy settings. Because we only use essential
                session cookies, clearing them will not permanently affect your
                ability to use the platform — your next visit will simply begin
                a new session.
              </p>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-[13px] font-semibold text-slate-200">
                Future Cookie Use
              </h3>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">
                If user account features are introduced in future, additional
                cookies may be required to maintain authenticated sessions and
                save preferences. Any such changes will be communicated clearly
                via the{" "}
                <Link
                  href="/whats-new"
                  className="text-emerald-400 underline-offset-2 hover:underline"
                >
                  What&apos;s New
                </Link>{" "}
                page, and users will be given the ability to review and accept
                updated cookie preferences before they take effect.
              </p>
            </div>
          </div>
        </section>
      </div>

      {/* Footer note */}
      <div className="mt-10 rounded-xl border border-white/[0.08] bg-white/[0.02] p-5">
        <p className="text-[12px] leading-6 text-slate-500">
          These legal documents were last updated in{" "}
          <span className="text-slate-400">July 2025</span>. For questions
          regarding any of the above, write to{" "}
          <a
            href="mailto:support@marketripple.in"
            className="text-sky-400 underline-offset-2 hover:underline"
          >
            support@marketripple.in
          </a>
          . MarketRipple is governed under the laws of India. Any disputes arising
          from use of this platform shall be subject to the exclusive
          jurisdiction of courts in India.
        </p>
      </div>
    </main>
  );
}
