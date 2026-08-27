import { CardListSkeleton } from "@/components/loading/Skeletons";

export default function Loading() {
  return <CardListSkeleton cards={4} columns={2} />;
}
