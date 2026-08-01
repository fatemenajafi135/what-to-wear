import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { RecommendChat } from "@/components/recommend/RecommendChat";

/**
 * design/design-system.md § Screen anatomy → Recommend. Chrome (TopHeader)
 * plus the whole chat surface (hero/chat states, composer, Start styling,
 * calendar context) built by feature 008 — see specs/008-styling-chat/.
 */
export default function RecommendPage() {
  return (
    <>
      <TopHeader
        title="Styling"
        subtitle="Ask for an outfit, get cited picks from your closet"
      />
      <RecommendChat />
    </>
  );
}
