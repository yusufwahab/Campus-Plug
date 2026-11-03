import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Badge } from "@/components/ui/Badge";

describe("components", () => {
  it("disables a loading button so it cannot double submit", async () => {
    const onClick = vi.fn();
    render(<Button loading onClick={onClick}>Pay</Button>);
    const btn = screen.getByRole("button", { name: /pay/i });
    expect(btn).toBeDisabled();
    await userEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });
  it("links the error message to the input", () => {
    render(<Input label="Phone" error="Invalid" />);
    expect(screen.getByLabelText("Phone")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid");
  });
  it("renders a status badge", () => {
    render(<Badge tone="verified">Verified</Badge>);
    expect(screen.getByText("Verified")).toHaveClass("bg-verified-bg");
  });
});
