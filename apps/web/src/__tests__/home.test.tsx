import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Home from "@/app/page";
import { cn } from "@/lib/utils";

describe("Home", () => {
  it("shows NO TRADE as the default for every card", () => {
    render(<Home />);
    expect(screen.getAllByText("NO TRADE")).toHaveLength(3);
  });
});

describe("cn", () => {
  it("merges conflicting Tailwind classes", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });
});
