"use client";

import { useRef, useEffect } from "react";

interface SearchBarProps {
  query: string;
  onChange: (value: string) => void;
}

export default function SearchBar({ query, onChange }: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === "Escape") {
        inputRef.current?.blur();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="relative max-w-3xl mx-auto">
      <div className="relative search-glow rounded-2xl bg-white/[0.045] backdrop-blur-xl border border-white/10 transition-all duration-200 focus-within:border-sky-400/50 focus-within:shadow-lg">
        <div className="flex items-center">
          {/* Search icon */}
          <div className="pl-5 pr-2 text-white/40">
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>

          {/* Input */}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Search logs, containers, apps, documents, configs across all servers..."
            className="flex-1 py-4 text-base text-white placeholder:text-white/35 bg-transparent outline-none"
            autoFocus
          />

          {/* Clear button */}
          {query && (
            <button
              onClick={() => onChange("")}
              className="mr-3 p-1.5 rounded-lg text-white/40 hover:text-white/80 hover:bg-white/10 transition-colors"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}

          {/* Keyboard shortcut hint */}
          {!query && (
            <div className="mr-4 hidden sm:flex items-center gap-1">
              <kbd className="inline-flex items-center px-2 py-0.5 text-[10px] font-mono text-white/50 bg-white/10 rounded border border-white/10">
                /
              </kbd>
              <span className="text-[10px] text-white/40">to focus</span>
            </div>
          )}
        </div>
      </div>

      {/* Search tips */}
      {!query && (
        <div className="mt-3 flex flex-wrap justify-center gap-2">
          {[
            "nginx errors",
            "postgresql slow",
            "docker container",
            "SSL certificate",
            "disk space",
            "redis cache",
          ].map((tip) => (
            <button
              key={tip}
              onClick={() => onChange(tip)}
              className="inline-flex items-center px-3 py-1.5 text-xs text-white/60 bg-white/[0.04] border border-white/10 rounded-full hover:border-sky-400/40 hover:text-sky-300 hover:bg-sky-400/10 transition-all duration-150"
            >
              {tip}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
