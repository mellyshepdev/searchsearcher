import { Suspense } from "react";
import SearchPage from "@/components/SearchPage";

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <div className="w-8 h-8 border-3 border-sky-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-white/50">Loading search platform...</p>
          </div>
        </div>
      }
    >
      <SearchPage />
    </Suspense>
  );
}
