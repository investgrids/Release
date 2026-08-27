import { CardListSkeleton } from "@/components/loading/Skeletons";

export default function Loading() {
  return <CardListSkeleton cards={6} columns={3} />;
}
