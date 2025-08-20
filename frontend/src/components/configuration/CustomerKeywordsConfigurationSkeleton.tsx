import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function CustomerKeywordsConfigurationSkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Customer Keywords</CardTitle>
        <CardDescription>
          Add keywords that describe your target customers to monitor relevant
          discussions.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Input skeleton */}
        <div className="flex gap-2">
          <Skeleton className="h-10 flex-1" />
          <Skeleton className="h-10 w-10" />
        </div>

        {/* Keywords skeleton */}
        <div className="flex flex-wrap gap-2">
          <Skeleton className="h-8 w-28 rounded-full" />
          <Skeleton className="h-8 w-32 rounded-full" />
          <Skeleton className="h-8 w-24 rounded-full" />
          <Skeleton className="h-8 w-36 rounded-full" />
          <Skeleton className="h-8 w-20 rounded-full" />
        </div>
      </CardContent>
    </Card>
  );
}
