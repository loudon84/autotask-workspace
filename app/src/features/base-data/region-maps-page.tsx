import { PageHeader } from "@/components/common/page-header";
import { RegionMapsPanel } from "@/features/region-maps/region-maps-panel";

export function RegionMapsPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        description="地区编号全 SRM 共用，各 SRM 显示名按需维护"
        title="原产地"
      />
      <RegionMapsPanel />
    </div>
  );
}
