"use client";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-xl space-y-4 p-8">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="muted">
        The page hit an unexpected error. Try again; if it keeps happening, check that the backend is running.
      </p>
      <button type="button" className="btn-primary" onClick={reset}>
        Try again
      </button>
    </div>
  );
}
