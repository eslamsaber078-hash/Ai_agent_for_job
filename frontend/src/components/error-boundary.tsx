import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface State {
  error: Error | null;
}

/** Keeps one broken screen from blanking the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI crashed:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-md rounded-xl border border-red-500/30 bg-card p-6 text-center shadow-sm">
          <AlertTriangle className="mx-auto h-5 w-5 text-red-500" aria-hidden />
          <h1 className="mt-4 text-[15px] font-semibold">This page hit an error</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Your saved data is safe. Reload to continue — if it keeps happening, restart the backend too.
          </p>
          <p className="mt-3 truncate text-xs text-muted-foreground/80">{this.state.error.message}</p>
          <div className="mt-5 flex justify-center gap-2">
            <Button size="sm" onClick={() => this.setState({ error: null })}>Try again</Button>
            <Button size="sm" variant="outline" onClick={() => location.reload()}>Reload</Button>
          </div>
        </div>
      </div>
    );
  }
}
