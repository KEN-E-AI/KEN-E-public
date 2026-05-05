import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { runAxe } from "./axe";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

describe("axe sweep — UI primitives", () => {
  it("Button: default variant has no violations", async () => {
    const { container } = render(<Button>Submit</Button>);
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Button: destructive variant has no violations", async () => {
    const { container } = render(<Button variant="destructive">Delete</Button>);
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Button: disabled state has no violations", async () => {
    const { container } = render(<Button disabled>Loading…</Button>);
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Button: outline variant has no violations", async () => {
    const { container } = render(
      <Button variant="outline">Create new organization</Button>,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Button: ghost variant has no violations", async () => {
    const { container } = render(<Button variant="ghost">Cancel</Button>);
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Input: unlabelled input (label wraps it) has no violations", async () => {
    const { container } = render(
      <label>
        Email
        <Input type="email" placeholder="you@example.com" />
      </label>,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Input: aria-label on standalone input has no violations", async () => {
    const { container } = render(
      <Input aria-label="Search" type="search" placeholder="Search…" />,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Alert (default): has no violations", async () => {
    const { container } = render(
      <Alert>
        <AlertTitle>Heads up!</AlertTitle>
        <AlertDescription>You can add components to your app.</AlertDescription>
      </Alert>,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Alert (destructive): has no violations", async () => {
    const { container } = render(
      <Alert variant="destructive">
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>Something went wrong.</AlertDescription>
      </Alert>,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Badge: default variant has no violations", async () => {
    const { container } = render(<Badge>New</Badge>);
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Card: with header + content has no violations", async () => {
    const { container } = render(
      <Card>
        <CardHeader>
          <CardTitle>Card title</CardTitle>
        </CardHeader>
        <CardContent>
          <p>Card body copy.</p>
        </CardContent>
      </Card>,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  // color-contrast is disabled in runAxe (JSDOM cannot resolve CSS vars); dark-mode
  // contrast for the active state is verified numerically in token-contrast.test.ts.
  it("TabsTrigger: inactive state has no violations", async () => {
    const { container } = render(
      <Tabs defaultValue="b">
        <TabsList>
          <TabsTrigger value="a">Overview</TabsTrigger>
          <TabsTrigger value="b">Details</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Overview content</TabsContent>
        <TabsContent value="b">Details content</TabsContent>
      </Tabs>,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("TabsTrigger: active state has no violations", async () => {
    const { container } = render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">Overview</TabsTrigger>
          <TabsTrigger value="b">Details</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Overview content</TabsContent>
        <TabsContent value="b">Details content</TabsContent>
      </Tabs>,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("TabsTrigger: disabled state has no violations", async () => {
    const { container } = render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">Overview</TabsTrigger>
          <TabsTrigger value="b" disabled>
            Details
          </TabsTrigger>
        </TabsList>
        <TabsContent value="a">Overview content</TabsContent>
        <TabsContent value="b">Details content</TabsContent>
      </Tabs>,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
