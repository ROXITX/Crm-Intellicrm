"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

export default function Index() {
  const { me, loading } = useAuth();
  const router = useRouter();
  useEffect(() => { if (!loading) router.replace(me ? (me.role === "client" ? "/portal" : "/dashboard") : "/login"); }, [me, loading, router]);
  return <div className="grid h-screen place-items-center text-ink-2" role="status">Loading...</div>;
}
