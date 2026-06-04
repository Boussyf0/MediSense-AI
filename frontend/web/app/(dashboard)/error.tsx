'use client';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <div className="text-center max-w-md">
        <div className="mb-4 text-4xl">⚠️</div>
        <h2 className="text-lg font-semibold text-white mb-2">
          Erreur de chargement
        </h2>
        <p className="text-gray-400 mb-4 text-sm">
          {error.message || 'Cette section n\'a pas pu être chargée.'}
        </p>
        <button
          onClick={reset}
          className="px-5 py-2 rounded-lg bg-white/10 text-white text-sm hover:bg-white/20 transition"
        >
          Réessayer
        </button>
      </div>
    </div>
  );
}
