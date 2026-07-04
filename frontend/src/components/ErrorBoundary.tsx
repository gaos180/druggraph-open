import React from 'react';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[DrugGraph] Error de componente:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', minHeight: '200px', padding: '2rem',
          color: '#ef4444', fontFamily: 'sans-serif',
        }}>
          <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Algo salió mal.</p>
          <p style={{ fontSize: '0.85rem', color: '#888', maxWidth: '400px', textAlign: 'center' }}>
            {this.state.error?.message ?? 'Error inesperado en este componente.'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              marginTop: '1rem', padding: '0.4rem 1rem',
              background: '#1e3a5f', color: '#fff', border: 'none',
              borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem',
            }}
          >
            Reintentar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
