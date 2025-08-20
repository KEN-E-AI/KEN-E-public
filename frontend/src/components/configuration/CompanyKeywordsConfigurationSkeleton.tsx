import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function CompanyKeywordsConfigurationSkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Company Keywords</CardTitle>
        <CardDescription>
          Add keywords that describe your company. These will be used to monitor
          news and social media mentions.
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
          <Skeleton className="h-8 w-24 rounded-full" />
          <Skeleton className="h-8 w-32 rounded-full" />
          <Skeleton className="h-8 w-20 rounded-full" />
          <Skeleton className="h-8 w-28 rounded-full" />
          <Skeleton className="h-8 w-36 rounded-full" />
          <Skeleton className="h-8 w-24 rounded-full" />
          <Skeleton className="h-8 w-30 rounded-full" />
          <Skeleton className="h-8 w-26 rounded-full" />
        </div>
      </CardContent>
    </Card>
  );
}
