import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState as useStateReact } from "react";
import { TargetingRulesEditor } from "./TargetingRulesEditor";
import type { TargetingRules } from "@/lib/featureFlags/types";

const emptyRules: TargetingRules = {
  user_emails: [],
  email_domains: [],
  organization_ids: [],
  account_ids: [],
  rollout_percentage: 0,
};

// Stateful wrapper so userEvent.type works correctly in controlled components
function StatefulEditor({
  initialValue = emptyRules,
  onChange: externalOnChange,
}: {
  initialValue?: TargetingRules;
  onChange?: (v: TargetingRules) => void;
}) {
  const [value, setValue] = useStateReact(initialValue);
  return (
    <TargetingRulesEditor
      value={value}
      onChange={(next) => {
        setValue(next);
        externalOnChange?.(next);
      }}
    />
  );
}

function renderEditor(value: TargetingRules = emptyRules, onChange = vi.fn()) {
  return {
    onChange,
    ...render(<StatefulEditor initialValue={value} onChange={onChange} />),
  };
}

describe("TargetingRulesEditor", () => {
  describe("labels and aria-labels", () => {
    it("renders all four list inputs with labels and aria-labels", () => {
      renderEditor();
      expect(screen.getByLabelText("User emails")).toBeInTheDocument();
      expect(screen.getByLabelText("Email domains")).toBeInTheDocument();
      expect(screen.getByLabelText("Organization IDs")).toBeInTheDocument();
      expect(screen.getByLabelText("Account IDs")).toBeInTheDocument();
    });

    it("renders the rollout slider with an aria-label", () => {
      renderEditor();
      expect(
        screen.getByRole("slider", { name: "Rollout percentage" }),
      ).toBeInTheDocument();
    });
  });

  describe("comma-separated parsing produces the same array as newline-separated", () => {
    it("parses comma-separated user_emails", () => {
      const onChange = vi.fn();
      renderEditor(emptyRules, onChange);
      const textarea = screen.getByLabelText("User emails");
      fireEvent.change(textarea, {
        target: { value: "alice@example.com,bob@example.com" },
      });
      const lastCall = onChange.mock.calls[
        onChange.mock.calls.length - 1
      ][0] as TargetingRules;
      expect(lastCall.user_emails).toEqual([
        "alice@example.com",
        "bob@example.com",
      ]);
    });

    it("parses newline-separated user_emails", () => {
      const onChange = vi.fn();
      renderEditor(emptyRules, onChange);
      const textarea = screen.getByLabelText("User emails");
      fireEvent.change(textarea, {
        target: { value: "alice@example.com\nbob@example.com" },
      });
      const lastCall = onChange.mock.calls[
        onChange.mock.calls.length - 1
      ][0] as TargetingRules;
      expect(lastCall.user_emails).toEqual([
        "alice@example.com",
        "bob@example.com",
      ]);
    });

    it("comma and newline produce identical arrays", () => {
      const onChangeComma = vi.fn();
      const onChangeNewline = vi.fn();

      const { unmount: unmountComma } = render(
        <StatefulEditor initialValue={emptyRules} onChange={onChangeComma} />,
      );
      fireEvent.change(screen.getByLabelText("User emails"), {
        target: { value: "x@a.com,y@b.com,z@c.com" },
      });
      unmountComma();

      render(
        <StatefulEditor initialValue={emptyRules} onChange={onChangeNewline} />,
      );
      fireEvent.change(screen.getByLabelText("User emails"), {
        target: { value: "x@a.com\ny@b.com\nz@c.com" },
      });

      const commaResult = (
        onChangeComma.mock.calls[
          onChangeComma.mock.calls.length - 1
        ][0] as TargetingRules
      ).user_emails;
      const newlineResult = (
        onChangeNewline.mock.calls[
          onChangeNewline.mock.calls.length - 1
        ][0] as TargetingRules
      ).user_emails;
      expect(commaResult).toEqual(newlineResult);
    });

    it("trims whitespace around entries", () => {
      const onChange = vi.fn();
      renderEditor(emptyRules, onChange);
      fireEvent.change(screen.getByLabelText("Email domains"), {
        target: { value: "  ken-e.ai , example.com  " },
      });
      const lastCall = onChange.mock.calls[
        onChange.mock.calls.length - 1
      ][0] as TargetingRules;
      expect(lastCall.email_domains).toEqual(["ken-e.ai", "example.com"]);
    });

    it("drops empty entries", () => {
      const onChange = vi.fn();
      renderEditor(emptyRules, onChange);
      fireEvent.change(screen.getByLabelText("Organization IDs"), {
        target: { value: "org1,,org2," },
      });
      const lastCall = onChange.mock.calls[
        onChange.mock.calls.length - 1
      ][0] as TargetingRules;
      expect(lastCall.organization_ids).toEqual(["org1", "org2"]);
    });
  });

  describe("slider", () => {
    it("renders slider with aria-valuenow reflecting the current value", () => {
      renderEditor({ ...emptyRules, rollout_percentage: 42 });
      const slider = screen.getByRole("slider", { name: "Rollout percentage" });
      expect(slider).toHaveAttribute("aria-valuenow", "42");
    });

    it("aria-valuenow is within [0, 100] for boundary values", () => {
      const { rerender } = render(
        <TargetingRulesEditor
          value={{ ...emptyRules, rollout_percentage: 0 }}
          onChange={vi.fn()}
        />,
      );
      expect(screen.getByRole("slider")).toHaveAttribute("aria-valuenow", "0");

      rerender(
        <TargetingRulesEditor
          value={{ ...emptyRules, rollout_percentage: 100 }}
          onChange={vi.fn()}
        />,
      );
      expect(screen.getByRole("slider")).toHaveAttribute(
        "aria-valuenow",
        "100",
      );
    });

    it("slider aria-valuemin is 0 and aria-valuemax is 100", () => {
      renderEditor();
      const slider = screen.getByRole("slider");
      expect(slider).toHaveAttribute("aria-valuemin", "0");
      expect(slider).toHaveAttribute("aria-valuemax", "100");
    });
  });

  describe("purely controlled — no internal state", () => {
    it("displays value from props, not internal state", () => {
      const { rerender } = render(
        <TargetingRulesEditor
          value={{ ...emptyRules, user_emails: ["a@b.com"] }}
          onChange={vi.fn()}
        />,
      );
      expect(screen.getByLabelText("User emails")).toHaveValue("a@b.com");
      // Updating the prop immediately reflects in the textarea (no internal state)
      rerender(
        <TargetingRulesEditor
          value={{ ...emptyRules, user_emails: ["c@d.com", "e@f.com"] }}
          onChange={vi.fn()}
        />,
      );
      expect(screen.getByLabelText("User emails")).toHaveValue(
        "c@d.com\ne@f.com",
      );
    });
  });
});
