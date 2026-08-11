import { useState } from "react";
import { MockLoading } from "@/components/common/mock-loading";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useRpaComponents } from "@/features/components/api/use-rpa-components";

const categories = [
  "全部",
  "浏览器组件",
  "页面操作组件",
  "表单组件",
  "文件组件",
  "等待/断言组件",
  "证据组件",
  "人工介入组件",
];

export function ComponentsPage() {
  const [category, setCategory] = useState("全部");

  const { data: components = [], isLoading } = useRpaComponents();

  const filtered =
    category === "全部"
      ? components
      : components.filter((c) => c.category === category);

  if (isLoading) {
    return <MockLoading />;
  }

  return (
    <div className="space-y-4">
      <PageHeader description="平台支持的原子 RPA 组件" title="RPA 组件库" />

      <Tabs onValueChange={setCategory} value={category}>
        <TabsList className="h-auto flex-wrap">
          {categories.map((cat) => (
            <TabsTrigger key={cat} value={cat}>
              {cat}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((comp) => (
          <Card key={comp.id}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">{comp.name}</CardTitle>
                <Badge variant="outline">{comp.category}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-sm">
                {comp.description}
              </p>
              <p className="mt-2 font-mono text-muted-foreground text-xs">
                {comp.type}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
