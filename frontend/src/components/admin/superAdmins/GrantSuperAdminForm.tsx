import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { GrantSuperAdminRequest } from "@/data/superAdminsApi";

type GrantMode = "email" | "uid";

type Props = {
  onGrant: (body: GrantSuperAdminRequest) => void;
  isPending: boolean;
  error: string | null;
};

export function GrantSuperAdminForm({ onGrant, isPending, error }: Props) {
  const [mode, setMode] = useState<GrantMode>("email");
  const [value, setValue] = useState("");

  const handleModeChange = (next: string) => {
    setMode(next as GrantMode);
    setValue("");
  };

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    if (mode === "email") {
      onGrant({ email: trimmed });
    } else {
      onGrant({ uid: trimmed });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSubmit();
  };

  return (
    <div className="space-y-3">
      <Tabs value={mode} onValueChange={handleModeChange}>
        <TabsList>
          <TabsTrigger value="email">By email</TabsTrigger>
          <TabsTrigger value="uid">By UID</TabsTrigger>
        </TabsList>
      </Tabs>
      <div className="flex gap-2">
        <Input
          type={mode === "email" ? "email" : "text"}
          placeholder={mode === "email" ? "user@example.com" : "Firebase UID"}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isPending}
          aria-label={mode === "email" ? "User email" : "User UID"}
        />
        <Button onClick={handleSubmit} disabled={!value.trim() || isPending}>
          {isPending ? "Granting…" : "Grant"}
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
