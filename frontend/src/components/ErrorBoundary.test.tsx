import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorBoundary } from './ErrorBoundary';

function Bomb({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('test error');
  return <div>OK</div>;
}

describe('ErrorBoundary', () => {
  let consoleErrorSpy: jest.SpyInstance;

  beforeEach(() => {
    // Suppress expected React error-boundary console output
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it('renders children normally when there is no error', () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow={false} />
      </ErrorBoundary>
    );
    expect(screen.getByText('OK')).toBeInTheDocument();
  });

  it('shows "Algo salió mal" message when a child throws', () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText(/Algo salió mal/i)).toBeInTheDocument();
  });

  it('resets the error state and re-renders children when Reintentar is clicked', () => {
    /**
     * BombHost controls whether Bomb throws via external state.
     * Sequence:
     *   1. Bomb throws → ErrorBoundary shows the fallback UI.
     *   2. Click "fix" → parent state changes (shouldThrow=false),
     *      but ErrorBoundary still holds hasError=true so fallback stays.
     *   3. Click "Reintentar" → ErrorBoundary resets its state,
     *      re-renders children; now Bomb no longer throws → "OK" appears.
     */
    function BombHost() {
      const [shouldThrow, setShouldThrow] = useState(true);
      return (
        <>
          <button onClick={() => setShouldThrow(false)}>fix</button>
          <ErrorBoundary>
            <Bomb shouldThrow={shouldThrow} />
          </ErrorBoundary>
        </>
      );
    }

    render(<BombHost />);

    // Error fallback is shown
    expect(screen.getByText(/Algo salió mal/i)).toBeInTheDocument();

    // Defuse the bomb so it won't throw on next render
    fireEvent.click(screen.getByText('fix'));

    // Reset the ErrorBoundary
    fireEvent.click(screen.getByText('Reintentar'));

    // Children render normally now
    expect(screen.getByText('OK')).toBeInTheDocument();
  });
});
