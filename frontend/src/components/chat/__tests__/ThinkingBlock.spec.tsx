import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThinkingBlock } from '../ThinkingBlock';

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...p }: any) => <div {...p}>{children}</div>,
    p: ({ children, ...p }: any) => <p {...p}>{children}</p>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

describe('ThinkingBlock', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('renders "Reasoning..." text when isThinking=true', () => {
    render(<ThinkingBlock isThinking={true} thoughts={[]} />);
    expect(screen.getByText('Reasoning...')).toBeInTheDocument();
  });

  test('renders singular "Thought for 1 second" when durationSeconds=1', () => {
    render(<ThinkingBlock isThinking={false} thoughts={[]} durationSeconds={1} />);
    expect(screen.getByText('Thought for 1 second')).toBeInTheDocument();
  });

  test('renders plural "Thought for N seconds" when durationSeconds !== 1', () => {
    render(<ThinkingBlock isThinking={false} thoughts={[]} durationSeconds={5} />);
    expect(screen.getByText('Thought for 5 seconds')).toBeInTheDocument();
  });

  test('renders "Thought for 0 seconds" when durationSeconds is omitted', () => {
    render(<ThinkingBlock isThinking={false} thoughts={[]} />);
    expect(screen.getByText('Thought for 0 seconds')).toBeInTheDocument();
  });

  test('stop button is not rendered when isThinking=false', () => {
    const onStop = vi.fn();
    render(<ThinkingBlock isThinking={false} thoughts={[]} onStop={onStop} />);
    expect(screen.queryByTitle('Stop generating')).not.toBeInTheDocument();
  });

  test('stop button is not rendered when isThinking=true but onStop is not provided', () => {
    render(<ThinkingBlock isThinking={true} thoughts={[]} />);
    expect(screen.queryByTitle('Stop generating')).not.toBeInTheDocument();
  });

  test('stop button renders when isThinking=true AND onStop is provided', () => {
    const onStop = vi.fn();
    render(<ThinkingBlock isThinking={true} thoughts={[]} onStop={onStop} />);
    expect(screen.getByTitle('Stop generating')).toBeInTheDocument();
  });

  test('stop button click calls onStop', () => {
    const onStop = vi.fn();
    render(<ThinkingBlock isThinking={true} thoughts={[]} onStop={onStop} />);

    fireEvent.click(screen.getByTitle('Stop generating'));

    expect(onStop).toHaveBeenCalledTimes(1);
  });

  test('stop button click does not toggle collapse (stopPropagation)', () => {
    const onStop = vi.fn();
    render(
      <ThinkingBlock isThinking={true} thoughts={['a thought']} onStop={onStop} />
    );

    // Content is visible initially (isOpen=true by default when isThinking=true)
    expect(screen.getByText('a thought')).toBeInTheDocument();

    fireEvent.click(screen.getByTitle('Stop generating'));

    // Content should still be visible — the click did not propagate to the toggle
    expect(screen.getByText('a thought')).toBeInTheDocument();
  });

  test('summary bar click toggles collapse', () => {
    render(
      <ThinkingBlock isThinking={true} thoughts={['a thought']} />
    );

    // The summary bar is a div[role="button"]; the Stop button is a <button>.
    // Query by role="button" returns all interactive elements; pick the outer one.
    const summaryBar = screen.getByRole('button', { name: /Reasoning/i });

    // Initially open — content visible
    expect(screen.getByText('a thought')).toBeInTheDocument();

    // Click to close
    fireEvent.click(summaryBar);
    expect(screen.queryByText('a thought')).not.toBeInTheDocument();

    // Click to open again
    fireEvent.click(summaryBar);
    expect(screen.getByText('a thought')).toBeInTheDocument();
  });
});
