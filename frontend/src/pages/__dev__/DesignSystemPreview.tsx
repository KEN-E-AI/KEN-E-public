import * as React from "react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Progress } from "@/components/ui/progress";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type PrimitiveBoxProps = {
  label: string;
  children: React.ReactNode;
};

function PrimitiveBox({ label, children }: PrimitiveBoxProps) {
  return (
    <div className="flex flex-col gap-2 p-4 rounded-[var(--radius-md)] border border-[var(--color-border-subtle)] bg-[var(--color-bg-primary)]">
      <span
        className="text-xs font-bold uppercase tracking-widest"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        {label}
      </span>
      <div className="flex flex-wrap gap-3 items-start">{children}</div>
    </div>
  );
}

type CategoryProps = {
  title: string;
  children: React.ReactNode;
};

function Category({ title, children }: CategoryProps) {
  return (
    <div className="flex flex-col gap-4">
      <h3
        className="text-base font-bold"
        style={{ color: "var(--color-text-secondary)" }}
      >
        {title}
      </h3>
      <div className="flex flex-col gap-3">{children}</div>
    </div>
  );
}

const VIEWPORT_WIDTHS = [375, 768, 1200, 1440, 1920] as const;

export function DesignSystemPreview() {
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [sheetOpen, setSheetOpen] = React.useState(false);

  return (
    <div
      className="min-h-screen py-8 px-6"
      style={{
        background: "var(--color-bg-primary)",
        color: "var(--color-text-primary)",
      }}
    >
      {/* Header strip */}
      <header
        className="flex items-center gap-4 mb-10 pb-6 border-b-2"
        style={{ borderColor: "var(--color-border-default)" }}
      >
        <ThemeToggle />
        <div className="flex flex-col gap-1">
          <h1
            className="text-2xl font-bold"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Design System Preview
          </h1>
          <p
            className="text-sm"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            Dev tooling only — not in production bundle. Reload iframes after
            toggling theme.
          </p>
        </div>
      </header>

      {/* Primitives section */}
      <section className="flex flex-col gap-10 mb-16">
        <h2
          className="text-xl font-bold"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Primitives
        </h2>

        {/* Layout */}
        <Category title="Layout">
          <PrimitiveBox label="Card">
            <Card className="w-64">
              <CardHeader>
                <CardTitle>Card Title</CardTitle>
                <CardDescription>
                  Card description text goes here.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p
                  className="text-sm"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  Card content area.
                </p>
              </CardContent>
            </Card>
          </PrimitiveBox>

          <PrimitiveBox label="Separator">
            <div className="flex flex-col gap-2 w-48">
              <span className="text-sm">Above</span>
              <Separator />
              <span className="text-sm">Below</span>
            </div>
            <div className="flex items-center gap-2 h-8">
              <span className="text-sm">Left</span>
              <Separator orientation="vertical" className="h-full" />
              <span className="text-sm">Right</span>
            </div>
          </PrimitiveBox>

          <PrimitiveBox label="ScrollArea">
            <ScrollArea className="h-32 w-48 rounded-[var(--radius-md)] border border-[var(--color-border-default)] p-3">
              {Array.from({ length: 10 }, (_, i) => (
                <p
                  key={i}
                  className="text-sm mb-1"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  Scroll item {i + 1}
                </p>
              ))}
            </ScrollArea>
          </PrimitiveBox>
        </Category>

        {/* Form */}
        <Category title="Form">
          <PrimitiveBox label="Button — variants">
            <Button variant="default">Default</Button>
            <Button variant="gradient">Gradient</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="link">Link</Button>
          </PrimitiveBox>

          <PrimitiveBox label="Button — sizes">
            <Button size="sm">Small</Button>
            <Button size="default">Default</Button>
            <Button size="lg">Large</Button>
            <Button size="icon" aria-label="icon button">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 5v14M5 12h14" />
              </svg>
            </Button>
          </PrimitiveBox>

          <PrimitiveBox label="Input">
            <Input className="w-64" placeholder="Enter text..." />
          </PrimitiveBox>

          <PrimitiveBox label="Textarea">
            <Textarea
              className="w-64"
              placeholder="Enter longer text..."
              rows={3}
            />
          </PrimitiveBox>

          <PrimitiveBox label="Select">
            <Select>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Select an option" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="option-1">Option 1</SelectItem>
                <SelectItem value="option-2">Option 2</SelectItem>
                <SelectItem value="option-3">Option 3</SelectItem>
              </SelectContent>
            </Select>
          </PrimitiveBox>

          <PrimitiveBox label="Checkbox">
            <div className="flex items-center gap-2">
              <Checkbox id="preview-checkbox" />
              <Label htmlFor="preview-checkbox">
                Accept terms and conditions
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox id="preview-checkbox-checked" defaultChecked />
              <Label htmlFor="preview-checkbox-checked">
                Checked by default
              </Label>
            </div>
          </PrimitiveBox>

          <PrimitiveBox label="RadioGroup">
            <RadioGroup defaultValue="option-a" className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <RadioGroupItem value="option-a" id="preview-radio-a" />
                <Label htmlFor="preview-radio-a">Option A</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="option-b" id="preview-radio-b" />
                <Label htmlFor="preview-radio-b">Option B</Label>
              </div>
            </RadioGroup>
          </PrimitiveBox>

          <PrimitiveBox label="Switch">
            <div className="flex items-center gap-2">
              <Switch id="preview-switch" />
              <Label htmlFor="preview-switch">Toggle feature</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch id="preview-switch-on" defaultChecked />
              <Label htmlFor="preview-switch-on">Enabled by default</Label>
            </div>
          </PrimitiveBox>

          <PrimitiveBox label="Form row (Label + Input)">
            <div className="flex flex-col gap-1.5 w-64">
              <Label htmlFor="preview-form-input">Email address</Label>
              <Input
                id="preview-form-input"
                type="email"
                placeholder="you@example.com"
              />
            </div>
          </PrimitiveBox>
        </Category>

        {/* Feedback */}
        <Category title="Feedback">
          <PrimitiveBox label="Alert">
            <div className="flex flex-col gap-3 w-full max-w-md">
              <Alert>
                <AlertTitle>Default alert</AlertTitle>
                <AlertDescription>
                  This is the default alert variant.
                </AlertDescription>
              </Alert>
              <Alert variant="destructive">
                <AlertTitle>Destructive alert</AlertTitle>
                <AlertDescription>
                  Something went wrong. Please try again.
                </AlertDescription>
              </Alert>
              <Alert variant="success">
                <AlertTitle>Success alert</AlertTitle>
                <AlertDescription>
                  Your changes have been saved.
                </AlertDescription>
              </Alert>
              <Alert variant="warning">
                <AlertTitle>Warning alert</AlertTitle>
                <AlertDescription>
                  Please review before continuing.
                </AlertDescription>
              </Alert>
              <Alert variant="info">
                <AlertTitle>Info alert</AlertTitle>
                <AlertDescription>
                  Here is some useful information.
                </AlertDescription>
              </Alert>
            </div>
          </PrimitiveBox>

          <PrimitiveBox label="Progress">
            <Progress value={60} className="w-[200px]" />
          </PrimitiveBox>

          <PrimitiveBox label="Skeleton">
            <div className="flex flex-col gap-2 w-48">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          </PrimitiveBox>
        </Category>

        {/* Overlay */}
        <Category title="Overlay">
          <PrimitiveBox label="Dialog">
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="outline">Open Dialog</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Dialog Title</DialogTitle>
                  <DialogDescription>
                    This is the dialog description. It provides context about
                    the action.
                  </DialogDescription>
                </DialogHeader>
                <div className="flex justify-end gap-2 mt-2">
                  <Button
                    variant="outline"
                    onClick={() => setDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button onClick={() => setDialogOpen(false)}>Confirm</Button>
                </div>
              </DialogContent>
            </Dialog>
          </PrimitiveBox>

          <PrimitiveBox label="Sheet">
            <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
              <SheetTrigger asChild>
                <Button variant="outline">Open Sheet</Button>
              </SheetTrigger>
              <SheetContent>
                <SheetHeader>
                  <SheetTitle>Sheet Title</SheetTitle>
                  <SheetDescription>
                    Sheet content slides in from the right edge.
                  </SheetDescription>
                </SheetHeader>
                <div className="mt-4">
                  <Button variant="outline" onClick={() => setSheetOpen(false)}>
                    Close
                  </Button>
                </div>
              </SheetContent>
            </Sheet>
          </PrimitiveBox>

          <PrimitiveBox label="Popover">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline">Open Popover</Button>
              </PopoverTrigger>
              <PopoverContent>
                <p
                  className="text-sm"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  Popover content appears here. It can contain any React nodes.
                </p>
              </PopoverContent>
            </Popover>
          </PrimitiveBox>

          <PrimitiveBox label="Tooltip">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="outline">Hover for tooltip</Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Tooltip content</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </PrimitiveBox>

          <PrimitiveBox label="DropdownMenu">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline">Open Menu</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuLabel>Actions</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Edit</DropdownMenuItem>
                <DropdownMenuItem>Duplicate</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Delete</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </PrimitiveBox>
        </Category>

        {/* Data Display */}
        <Category title="Data Display">
          <PrimitiveBox label="Table">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell>Campaign Alpha</TableCell>
                  <TableCell>Active</TableCell>
                  <TableCell>$4,200</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Campaign Beta</TableCell>
                  <TableCell>Paused</TableCell>
                  <TableCell>$1,800</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </PrimitiveBox>

          <PrimitiveBox label="Badge — variants">
            <Badge variant="default">Default</Badge>
            <Badge variant="secondary">Secondary</Badge>
            <Badge variant="destructive">Destructive</Badge>
            <Badge variant="outline">Outline</Badge>
          </PrimitiveBox>

          <PrimitiveBox label="Avatar">
            <Avatar>
              <AvatarFallback>KE</AvatarFallback>
            </Avatar>
            <Avatar>
              <AvatarFallback>JD</AvatarFallback>
            </Avatar>
          </PrimitiveBox>

          <PrimitiveBox label="Breadcrumb">
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbLink href="#">Home</BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbLink href="#">Settings</BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>Account</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </PrimitiveBox>

          <PrimitiveBox label="Accordion">
            <Accordion type="single" defaultValue="item-1" className="w-72">
              <AccordionItem value="item-1">
                <AccordionTrigger>What is KEN-E?</AccordionTrigger>
                <AccordionContent>
                  KEN-E is a multi-agent AI system for marketing analysis.
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </PrimitiveBox>
        </Category>

        {/* Navigation */}
        <Category title="Navigation">
          <PrimitiveBox label="Tabs">
            <Tabs defaultValue="overview" className="w-full max-w-md">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="performance">Performance</TabsTrigger>
                <TabsTrigger value="settings">Settings</TabsTrigger>
              </TabsList>
              <TabsContent value="overview">
                <p
                  className="text-sm pt-2"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  Overview tab content.
                </p>
              </TabsContent>
              <TabsContent value="performance">
                <p
                  className="text-sm pt-2"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  Performance tab content.
                </p>
              </TabsContent>
              <TabsContent value="settings">
                <p
                  className="text-sm pt-2"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  Settings tab content.
                </p>
              </TabsContent>
            </Tabs>
          </PrimitiveBox>

          <PrimitiveBox label="NavigationMenu">
            <NavigationMenu>
              <NavigationMenuList>
                <NavigationMenuItem>
                  <NavigationMenuLink
                    href="#"
                    className={navigationMenuTriggerStyle()}
                  >
                    Dashboard
                  </NavigationMenuLink>
                </NavigationMenuItem>
                <NavigationMenuItem>
                  <NavigationMenuLink
                    href="#"
                    className={navigationMenuTriggerStyle()}
                  >
                    Performance
                  </NavigationMenuLink>
                </NavigationMenuItem>
              </NavigationMenuList>
            </NavigationMenu>
          </PrimitiveBox>

          <PrimitiveBox label="Pagination">
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious href="#" />
                </PaginationItem>
                <PaginationItem>
                  <PaginationLink href="#" isActive>
                    1
                  </PaginationLink>
                </PaginationItem>
                <PaginationItem>
                  <PaginationLink href="#">2</PaginationLink>
                </PaginationItem>
                <PaginationItem>
                  <PaginationLink href="#">3</PaginationLink>
                </PaginationItem>
                <PaginationItem>
                  <PaginationNext href="#" />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </PrimitiveBox>
        </Category>
      </section>

      {/* Shell at viewport widths section */}
      <section className="flex flex-col gap-8">
        <h2
          className="text-xl font-bold"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Shell at viewport widths
        </h2>
        <div className="flex flex-col gap-8">
          {VIEWPORT_WIDTHS.map((width) => (
            <div key={width} className="flex flex-col gap-2">
              <span
                className="text-sm font-bold"
                style={{ color: "var(--color-text-tertiary)" }}
              >
                {width}px
              </span>
              <iframe
                src="/"
                loading="lazy"
                width={width}
                height={600}
                title={`Shell preview at ${width}px`}
                style={{
                  border: `2px solid var(--color-border-default)`,
                  borderRadius: "var(--radius-md)",
                  display: "block",
                  maxWidth: "100%",
                }}
              />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
