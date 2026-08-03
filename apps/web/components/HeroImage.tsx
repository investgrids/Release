import Image from "next/image";
import { ArticleArt } from "@/components/ArticleArt";
import { API_BASE_URL as API } from "@/lib/api";

/**
 * Real AI-generated hero image when one exists (see the backend's
 * GeneratedMedia pipeline), the gradient/icon artwork otherwise — never a
 * broken image, never a loading spinner blocking the page. hero_image_url
 * is only ever set once generation actually succeeds, so its mere
 * presence is the "ready" signal; there's no separate loading state to
 * thread through here.
 *
 * Uses next/image now that the backend media origin is allowlisted in
 * next.config.ts's remotePatterns (previously a raw <img> with no width/
 * height — a real, measured CLS source). `fill` inside an aspect-ratio
 * wrapper reserves layout space before the image loads, so this component
 * still expects the caller's className to size the wrapper (as it always
 * did) — only the img tag itself changed.
 */
export function HeroImage({
  heroImageUrl, headline, articleType, sectors = [], className = "",
}: {
  heroImageUrl?: string | null;
  headline: string;
  articleType: string;
  sectors?: string[];
  className?: string;
}) {
  if (heroImageUrl) {
    return (
      <div className={`relative overflow-hidden ${className}`}>
        <Image
          src={`${API}${heroImageUrl}`}
          alt={headline}
          fill
          sizes="(max-width: 768px) 100vw, 768px"
          className="object-cover"
          loading="lazy"
        />
      </div>
    );
  }
  return <ArticleArt headline={headline} articleType={articleType} sectors={sectors} className={className} />;
}
