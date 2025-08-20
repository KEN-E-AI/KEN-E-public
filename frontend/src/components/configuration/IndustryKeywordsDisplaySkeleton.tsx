import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function IndustryKeywordsDisplaySkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Industry Keywords</CardTitle>
        <CardDescription>
          <Skeleton className="h-4 w-64" />
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          <Skeleton className="h-8 w-24 rounded-full" />
          <Skeleton className="h-8 w-32 rounded-full" />
          <Skeleton className="h-8 w-28 rounded-full" />
          <Skeleton className="h-8 w-36 rounded-full" />
          <Skeleton className="h-8 w-20 rounded-full" />
          <Skeleton className="h-8 w-30 rounded-full" />
          <Skeleton className="h-8 w-26 rounded-full" />
          <Skeleton className="h-8 w-34 rounded-full" />
        </div>
      </CardContent>
    </Card>
  );
}
