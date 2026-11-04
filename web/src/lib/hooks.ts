"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, api } from "./api";
import { useToast } from "@/components/ui/Toast";

/** Debounces a fast-changing value such as a search box. */
export function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

/** Fetches an authenticated list and exposes the standard loading / error / retry fields. */
export function useApiQuery<T>(key: unknown[], path: string, query?: Record<string, string | number | boolean | undefined | null>) {
  return useQuery({ queryKey: [...key, query], queryFn: () => api<T>(path, { query }), placeholderData: (prev) => prev });
}

/** Runs a mutation, refreshes the given query keys, and shows a toast. Returns a function usable from buttons and modals. */
export function useAction(invalidate: unknown[][]) {
  const client = useQueryClient();
  const toast = useToast();
  return async (method: "POST" | "PUT" | "PATCH" | "DELETE", path: string, body: unknown, done: string, query?: Record<string, string | number | boolean>) => {
    try {
      const result = await api(path, { method, body, query });
      await Promise.all(invalidate.map((queryKey) => client.invalidateQueries({ queryKey })));
      toast(done);
      return result;
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Something went wrong", "error");
      throw e;
    }
  };
}
