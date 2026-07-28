import { redirect } from "next/navigation";

/**
 * /research is currently just the comparisons hub in disguise — the same
 * content the new /research/comparisons hub now serves, organized (SEO
 * roadmap: "don't show hundreds of pages as a flat list, surface them
 * contextually"). Once other real research content types exist (articles,
 * guides, historical patterns each already have their own real routes —
 * /newsroom, /learn/guides — this becomes a genuine cross-type index
 * instead of a redirect. Until then, a permanent redirect avoids two URLs
 * serving near-duplicate content, the exact "page with redirect"/duplicate-
 * content pattern this session's SEO audit fixed elsewhere.
 */
export default function ResearchIndexPage() {
  redirect("/research/comparisons");
}
