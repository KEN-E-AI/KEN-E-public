import { useState } from "react";
import { CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";

type RotateCodeRequest = {
  code: string;
  expires_at?: string | null;
  is_active?: boolean;
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRotate: (req: RotateCodeRequest) => void;
  isPending: boolean;
  serverError?: string | null;
};

export function RotateCodeDialog({
  open,
  onOpenChange,
  onRotate,
  isPending,
  serverError,
}: Props) {
  const [code, setCode] = useState("");
  const [expiryDate, setExpiryDate] = useState<Date | undefined>(undefined);
  const [disableOnRotate, setDisableOnRotate] = useState(false);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [codeError, setCodeError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = code.trim();
    if (!trimmed) {
      setCodeError("Code is required.");
      return;
    }
    if (trimmed.length > 256) {
      setCodeError("Code must be 256 characters or fewer.");
      return;
    }
    setCodeError(null);
    const req: RotateCodeRequest = {
      code: trimmed,
      expires_at: expiryDate ? expiryDate.toISOString() : null,
      ...(disableOnRotate ? { is_active: false } : {}),
    };
    onRotate(req);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setCode("");
      setExpiryDate(undefined);
      setDisableOnRotate(false);
      setCodeError(null);
    }
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Set / Rotate Code</DialogTitle>
          <DialogDescription>
            Enter the new Early Release access code. This replaces the current
            code immediately.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="er-code">New code</Label>
            <Input
              id="er-code"
              type="text"
              placeholder="Enter access code"
              value={code}
              onChange={(e) => {
                setCode(e.target.value);
                setCodeError(null);
              }}
              aria-describedby={codeError ? "er-code-error" : undefined}
              disabled={isPending}
            />
            {codeError && (
              <p
                id="er-code-error"
                className="text-sm text-[var(--color-destructive)]"
              >
                {codeError}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Expiry date (optional)</Label>
            <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
              <PopoverTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className={cn(
                    "w-full justify-start text-left font-normal",
                    !expiryDate && "text-muted-foreground",
                  )}
                  disabled={isPending}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {expiryDate ? format(expiryDate, "PPP") : "No expiry"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={expiryDate}
                  onSelect={(date) => {
                    setExpiryDate(date ?? undefined);
                    setCalendarOpen(false);
                  }}
                  disabled={(date) => {
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);
                    return date < today;
                  }}
                  initialFocus
                />
                {expiryDate && (
                  <div className="p-2 border-t">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="w-full"
                      onClick={() => {
                        setExpiryDate(undefined);
                        setCalendarOpen(false);
                      }}
                    >
                      Clear expiry
                    </Button>
                  </div>
                )}
              </PopoverContent>
            </Popover>
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="er-disable"
              checked={disableOnRotate}
              onCheckedChange={(checked) =>
                setDisableOnRotate(checked === true)
              }
              disabled={isPending}
            />
            <Label htmlFor="er-disable" className="cursor-pointer">
              Disable code immediately after rotation
            </Label>
          </div>

          {serverError && (
            <p className="text-sm text-[var(--color-destructive)]">
              {serverError}
            </p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || !code.trim()}>
              {isPending ? "Rotating…" : "Rotate code"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
