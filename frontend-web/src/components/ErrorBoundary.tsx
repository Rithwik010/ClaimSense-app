// A page that fails to render shows a plain message instead of a blank screen; moving to another
// page clears it.

import { Component, type ReactNode } from "react";

interface State {
  failed: boolean;
}

export class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidUpdate(previous: { resetKey: string }) {
    if (previous.resetKey !== this.props.resetKey && this.state.failed) {
      this.setState({ failed: false });
    }
  }

  render() {
    if (this.state.failed) {
      return (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800">
          This page could not be shown. Reload the page; if it happens again, check that the API is
          running (make demo).
        </div>
      );
    }
    return this.props.children;
  }
}
