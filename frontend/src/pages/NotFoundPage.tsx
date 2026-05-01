import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Home } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";

export function NotFoundPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    console.warn("404: page not found:", location.pathname);
  }, [location.pathname]);

  const inner = (
    <div
      className={cn(
        "flex flex-col items-center justify-center p-8 text-center",
        !isAuthenticated && "min-h-screen",
      )}
    >
      <h1 className="mb-4">404 - Page Not Found</h1>
      <p className="text-muted-foreground mb-6">
        The page you&apos;re looking for doesn&apos;t exist.
      </p>
      <Button onClick={() => navigate("/")}>
        <Home className="size-4 mr-2" />
        Back to Home
      </Button>
    </div>
  );

  return inner;
}

export default NotFoundPage;
