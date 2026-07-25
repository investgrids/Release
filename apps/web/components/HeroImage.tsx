import { ArticleArt } from "@/components/ArticleArt";
import { API_BASE_URL as API } from "@/lib/api";

/**
 * Real AI-generated hero image when one exists (see the backend's
 * GeneratedMedia pipeline), the gradient/icon artwork otherwise — never a
 * broken image, never a loading spinner blocking the page. hero_image_url
 * is only ever set once generation actually succeeds, so its mere
 * presence is the "ready" signal; there's no separate loading state to
 * thread through here.
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
      // eslint-disable-next-line @next/next/no-img-element -- external/self-hosted
      // media path (backend-served, not in the Next.js image loader's domain
      // list), and this is a low-volume feed (a few images/day), not a
      // performance-critical image gallery — next/image's build-time
      // optimization isn't worth the extra config here.
      <img
        src={`${API}${heroImageUrl}`}
        alt={headline}
        className={`object-cover ${className}`}
        loading="lazy"
      />
    );
  }
  return <ArticleArt headline={headline} articleType={articleType} sectors={sectors} className={className} />;
}
