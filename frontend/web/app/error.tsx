'use client';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0A0D14]">
      <div className="text-center max-w-md px-6">
        <div className="mb-6 text-5xl">⚕️</div>
        <h2 className="text-xl font-semibold text-white mb-2">
          Une erreur est survenue
        </h2>
        <p className="text-gray-400 mb-6 text-sm">
          {error.message || 'Veuillez réessayer ou contacter le support.'}
        </p>
        <button
          onClick={reset}
          className="px-6 py-2.5 rounded-full bg-gradient-to-r from-purple-600 to-blue-500 text-white text-sm font-medium hover:opacity-90 transition"
        >
          Réessayer
        </button>
      </div>
    </div>
  );
}
