"use client";

import { useState, useEffect, useCallback } from "react";
import { AnimatePresence } from "framer-motion";
import { DashboardHero } from "@/components/DashboardHero";
import { WelcomeBackHero } from "@/components/dashboard/WelcomeBackHero";
import { FirstVisitBanner } from "@/components/onboarding/FirstVisitBanner";

interface HeroStats {
  sentimentScore: number; sentimentLabel: string; sentimentChange: string;
  eventsToday: number;    eventsTodayVs: string;
  highImpactEvents: number; highImpactVs: string;
  opportunityScore: number; opportunityVs: string;
  aiConfidence: number;   aiConfidenceLabel: string; aiConfidenceVs: string;
}

interface SmartHeroProps {
  date: string;
  status: "Market Open" | "Market Closed";
  greeting: string;
  timeIST: string;
  stats: HeroStats;
}

/**
 * SmartHero: switches between first-visit and returning-user experiences.
 *
 * - null   (hydrating): renders DashboardHero to avoid layout shift
 * - first  (new user): renders DashboardHero + FirstVisitBanner above it
 * - returning (known user): renders WelcomeBackHero with ContinueResearch
 *
 * Future: replace localStorage.getItem("marketripple_onboarded") with a session
 * check against the auth API once accounts are added.
 */
export function SmartHero(props: SmartHeroProps) {
  const [state, setState] = useState<"idle" | "first" | "returning">("idle");

  useEffect(() => {
    try {
      const onboarded = localStorage.getItem("marketripple_onboarded") === "true";
      setState(onboarded ? "returning" : "first");
    } catch {
      setState("returning");
    }
  }, []);

  const handleDismiss = useCallback(() => {
    try { localStorage.setItem("marketripple_onboarded", "true"); } catch {}
    setState("returning");
  }, []);

  // idle: brief hydration window — show normal hero to avoid layout shift
  if (state === "idle") {
    return <DashboardHero {...props} />;
  }

  // returning user: personalised hero with recent history
  if (state === "returning") {
    return <WelcomeBackHero {...props} />;
  }

  // first-time user: welcome banner as top-right overlay, hero renders normally
  return (
    <>
      <AnimatePresence>
        <FirstVisitBanner onDismiss={handleDismiss} />
      </AnimatePresence>
      <DashboardHero {...props} />
    </>
  );
}
