import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusPill } from "@/components/status-pill";

describe("StatusPill", () => {
  it("labels healthy and unhealthy states", () => {
    render(
      <>
        <StatusPill ok label="Operational" />
        <StatusPill ok={false} label="Down" />
      </>,
    );
    expect(screen.getByText("Operational")).toBeInTheDocument();
    expect(screen.getByText("Down")).toBeInTheDocument();
  });
});
