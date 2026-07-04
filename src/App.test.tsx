import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the empty state with suggestion chips", () => {
    render(<App />);

    expect(screen.getByText("What can I help with?")).toBeInTheDocument();
    expect(screen.getByText("What can you help me with?")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ask something...")).toBeInTheDocument();
  });
});
