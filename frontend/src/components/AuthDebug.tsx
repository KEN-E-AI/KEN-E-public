import { useState } from "react";
import { auth } from "@/lib/firebase";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AuthDebug() {
  const [debugInfo, setDebugInfo] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);

  const runDebugChecks = async () => {
    setIsLoading(true);
    let info = "=== Authentication Debug Info ===\n\n";

    try {
      // Check 1: Firebase user
      info += "1. Firebase User:\n";
      const user = auth.currentUser;
      if (user) {
        info += `   - UID: ${user.uid}\n`;
        info += `   - Email: ${user.email}\n`;
        info += `   - Email Verified: ${user.emailVerified}\n`;

        // Check 2: Get ID token
        info += "\n2. ID Token:\n";
        try {
          const token = await user.getIdToken();
          info += `   - Token obtained: Yes\n`;
          info += `   - Token length: ${token.length}\n`;
          info += `   - Token preview: ${token.substring(0, 20)}...\n`;

          // Check 3: Test API call with manual header
          info += "\n3. Manual API Test:\n";
          try {
            const response = await fetch(
              `${import.meta.env.VITE_API_BASE_URL}/api/v1/accounts/`,
              {
                headers: {
                  Authorization: `Bearer ${token}`,
                  "Content-Type": "application/json",
                },
              },
            );
            info += `   - Status: ${response.status}\n`;
            const data = await response.json();
            info += `   - Response: ${JSON.stringify(data, null, 2)}\n`;
          } catch (e) {
            info += `   - Error: ${e}\n`;
          }

          // Check 4: Test API call with axios
          info += "\n4. Axios API Test:\n";
          try {
            const response = await api.get("/api/v1/accounts/");
            info += `   - Status: ${response.status}\n`;
            info += `   - Data: ${JSON.stringify(response.data, null, 2)}\n`;
          } catch (e: any) {
            info += `   - Error: ${e.message}\n`;
            if (e.response) {
              info += `   - Status: ${e.response.status}\n`;
              info += `   - Data: ${JSON.stringify(e.response.data, null, 2)}\n`;
            }
          }
        } catch (e) {
          info += `   - Error getting token: ${e}\n`;
        }
      } else {
        info += "   - No user logged in\n";
      }

      // Check 5: Environment
      info += "\n5. Environment:\n";
      info += `   - API URL: ${import.meta.env.VITE_API_BASE_URL}\n`;
      info += `   - Environment: ${import.meta.env.VITE_ENVIRONMENT}\n`;
    } catch (error) {
      info += `\nUnexpected error: ${error}\n`;
    }

    setDebugInfo(info);
    setIsLoading(false);
  };

  return (
    <Card className="m-4">
      <CardHeader>
        <CardTitle>Authentication Debug</CardTitle>
      </CardHeader>
      <CardContent>
        <Button onClick={runDebugChecks} disabled={isLoading}>
          {isLoading ? "Running..." : "Run Debug Checks"}
        </Button>
        {debugInfo && (
          <pre className="mt-4 p-4 bg-gray-100 rounded text-xs overflow-auto">
            {debugInfo}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}
