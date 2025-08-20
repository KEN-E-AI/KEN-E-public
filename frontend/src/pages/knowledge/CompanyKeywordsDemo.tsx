import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import CompanyKeywordsConfiguration from "@/components/configuration/CompanyKeywordsConfiguration";
import CompanyKeywordsConfigurationPaginated from "@/components/configuration/CompanyKeywordsConfigurationPaginated";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Info } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function CompanyKeywordsDemo() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Company Keywords Configuration</h1>
        <p className="text-muted-foreground mt-2">
          Compare the original and paginated versions of the company keywords
          configuration.
        </p>
      </div>

      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>
          The paginated version is recommended for accounts with 100+ keywords.
          It provides better performance, search functionality, and a cleaner
          user experience for large datasets.
        </AlertDescription>
      </Alert>

      <Tabs defaultValue="paginated" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="original">Original Version</TabsTrigger>
          <TabsTrigger value="paginated">
            Paginated Version (Recommended)
          </TabsTrigger>
        </TabsList>

        <TabsContent value="original" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Original Implementation</CardTitle>
              <CardDescription>
                Displays all keywords at once. May experience performance issues
                with large datasets.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <p>✅ Simple implementation</p>
                <p>✅ Immediate visibility of all keywords</p>
                <p>❌ Performance degradation with 100+ keywords</p>
                <p>❌ No search functionality</p>
                <p>❌ Difficult to manage large lists</p>
              </div>
            </CardContent>
          </Card>
          <CompanyKeywordsConfiguration />
        </TabsContent>

        <TabsContent value="paginated" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Paginated Implementation</CardTitle>
              <CardDescription>
                Displays keywords in pages with search and configurable page
                size.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <p>✅ Excellent performance with any dataset size</p>
                <p>✅ Built-in search functionality</p>
                <p>✅ Configurable page size (20, 50, 100, 200)</p>
                <p>✅ Smooth navigation between pages</p>
                <p>✅ Better user experience for large lists</p>
                <p>❌ Slightly more complex implementation</p>
              </div>
            </CardContent>
          </Card>
          <CompanyKeywordsConfigurationPaginated />
        </TabsContent>
      </Tabs>

      <Card className="border-dashed">
        <CardHeader>
          <CardTitle>Implementation Notes</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h3 className="font-semibold mb-2">Performance Considerations</h3>
            <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
              <li>
                The paginated version renders only visible keywords, reducing
                DOM size
              </li>
              <li>
                Search is performed server-side, reducing client processing
              </li>
              <li>
                Page size can be adjusted based on user preference and device
                capabilities
              </li>
            </ul>
          </div>

          <div>
            <h3 className="font-semibold mb-2">User Experience Improvements</h3>
            <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
              <li>
                Keywords are added/removed immediately without a separate save
                step
              </li>
              <li>Search helps users quickly find specific keywords</li>
              <li>Pagination controls are intuitive with numbered pages</li>
              <li>Loading states provide clear feedback during operations</li>
            </ul>
          </div>

          <div>
            <h3 className="font-semibold mb-2">API Integration</h3>
            <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
              <li>
                New endpoint: GET /monitoring-topics/{"{account_id}"}
                /company/paginated
              </li>
              <li>Supports query parameters: page, page_size, search</li>
              <li>Returns paginated response with metadata</li>
              <li>Backward compatible with existing update endpoints</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
