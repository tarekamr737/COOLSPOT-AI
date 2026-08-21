import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "@/app/page";

describe("Home", () => {
  it("renders the golden map information architecture", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { name: "Pacoima" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Ranked recommendations" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Van Nuys / Herrick" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Map layer hierarchy")).toBeInTheDocument();
    expect(screen.getByLabelText("Cached data status")).toHaveTextContent(
      "1,991,560 FortyGuard credits remaining",
    );
    expect(screen.getByText(/it is not a temperature forecast/i)).toBeInTheDocument();
  });
});
