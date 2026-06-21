import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="history-error">
            页面渲染出错：{this.state.error.message}
            <button
              type="button"
              className="btn-secondary"
              style={{ marginLeft: 12 }}
              onClick={() => this.setState({ error: null })}
            >
              重试
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
