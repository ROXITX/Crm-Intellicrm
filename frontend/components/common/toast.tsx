"use client";
import { createContext, useCallback, useContext, useState } from "react";

type T = { id: number; text: string; tone: "ok" | "err" };
const Ctx = createContext<(text: string, tone?: "ok" | "err") => void>(() => {});
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<T[]>([]);
  const push = useCallback((text: string, tone: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, tone }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 4000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] space-y-2" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className={`rounded-ctl border bg-surface px-3.5 py-2.5 text-[13px] shadow-pop ${i.tone === "err" ? "border-danger text-danger" : "border-line"}`}>{i.text}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
