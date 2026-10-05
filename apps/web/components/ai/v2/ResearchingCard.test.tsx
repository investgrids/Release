// Step 7 follow-up: the researching card shows only true things (question, real timer, real stages) and no fake progress.
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ResearchingCard } from "./ResearchingCard";

afterEach(() => { vi.useRealTimers(); });

describe("ResearchingCard", () => {
  it("without stage events shows the question, a timer and one plain line, no step list and no percentage", () => {
    const { container } = render(<ResearchingCard query="What is happening with Wipro?" />);
    expect(screen.getByTestId("working-query")).toHaveTextContent("What is happening with Wipro?");
    expect(screen.getByTestId("working-elapsed")).toHaveTextContent("0.0s");
    expect(screen.queryByTestId("working-stages")).toBeNull();
    expect(container.textContent).not.toMatch(/\d+\s*%/);
  });

  it("with stages: earlier stages are done with their real times, the last one is in progress with no time", () => {
    render(<ResearchingCard query="q" stages={[
      { stage: "intent", label: "Understanding your question", elapsedMs: 800 },
      { stage: "evidence", label: "Gathering evidence", elapsedMs: 2300 },
      { stage: "reasoning", label: "Writing the answer", elapsedMs: 4100 },
    ]} />);
    const list = screen.getByTestId("working-stages");
    expect(list).toHaveTextContent("Understanding your question");
    expect(list).toHaveTextContent("0.8s");
    expect(list).toHaveTextContent("2.3s");
    expect(list).not.toHaveTextContent("4.1s");          // the current stage has not finished, so it has no time
    expect(list.querySelector('[aria-current="step"]')).toHaveTextContent("Writing the answer");
  });

  it("counts real elapsed time and says so plainly once it is slow", () => {
    vi.useFakeTimers();
    render(<ResearchingCard query="q" />);
    expect(screen.queryByTestId("working-slow")).toBeNull();
    act(() => { vi.advanceTimersByTime(16000); });
    expect(screen.getByTestId("working-slow")).toHaveTextContent(/longer than usual/);
    expect(Number.parseFloat(screen.getByTestId("working-elapsed").textContent ?? "0")).toBeGreaterThanOrEqual(15);
  });

  it("is an announced status region", () => {
    render(<ResearchingCard query="q" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
