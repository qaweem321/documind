import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl space-y-4 p-8">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <Link href="/" className="btn-primary">
        Go to DocuMind
      </Link>
    </div>
  );
}
