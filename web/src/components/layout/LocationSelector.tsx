"use client";
import { useQuery } from "@tanstack/react-query";
import { MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ErrorState } from "@/components/ui/States";
import { Skeleton } from "@/components/ui/Skeleton";

export type Place = { campusSlug: string; campusName: string; locationId: number | null; locationName: string };
type Campus = { id: number; slug: string; name: string };
type Location = { id: number; name: string; campus_id: number };

const KEY = "cp_place";
export const DEFAULT_PLACE: Place = { campusSlug: "unilag", campusName: "UNILAG", locationId: null, locationName: "All of campus" };

export function usePlace() {
  const [place, setPlaceState] = useState<Place>(DEFAULT_PLACE);
  useEffect(() => {
    const raw = window.localStorage.getItem(KEY);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate from localStorage after mount
    if (raw) setPlaceState(JSON.parse(raw) as Place);
  }, []);
  const setPlace = (p: Place) => {
    window.localStorage.setItem(KEY, JSON.stringify(p));
    setPlaceState(p);
  };
  return [place, setPlace] as const;
}

export function LocationSelector() {
  const [open, setOpen] = useState(false);
  const [place, setPlace] = usePlace();
  const campuses = useQuery({ queryKey: ["campuses"], queryFn: () => api<Campus[]>("/campuses"), enabled: open });
  const locations = useQuery({ queryKey: ["locations"], queryFn: () => api<Location[]>("/locations"), enabled: open });
  const campus = campuses.data?.find((c) => c.slug === place.campusSlug) ?? campuses.data?.[0];

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-full border border-line bg-white px-4 text-sm font-semibold"
      >
        <MapPin className="size-4" aria-hidden="true" />
        <span className="max-w-32 truncate">
          {place.campusName} · {place.locationName}
        </span>
      </button>
      <Modal open={open} title="Choose your location" onClose={() => setOpen(false)}>
        {(campuses.isPending || locations.isPending) && !campuses.isError && (
          <div className="space-y-2">
            <Skeleton className="h-11" />
            <Skeleton className="h-11" />
            <Skeleton className="h-11" />
          </div>
        )}
        {(campuses.isError || locations.isError) && (
          <ErrorState message="Locations could not be loaded." onRetry={() => { void campuses.refetch(); void locations.refetch(); }} />
        )}
        {campus && locations.data && (
          <div>
            <p className="mb-3 text-sm text-muted">{campus.name}</p>
            <ul className="grid max-h-[50dvh] grid-cols-1 gap-2 overflow-y-auto md:grid-cols-2">
              <li>
                <Button
                  variant="tertiary"
                  className="w-full justify-start"
                  onClick={() => {
                    setPlace({ campusSlug: campus.slug, campusName: campus.name, locationId: null, locationName: "All of campus" });
                    setOpen(false);
                  }}
                >
                  All of campus
                </Button>
              </li>
              {locations.data
                .filter((l) => l.campus_id === campus.id)
                .map((l) => (
                  <li key={l.id}>
                    <Button
                      variant={place.locationId === l.id ? "primary" : "tertiary"}
                      className="w-full justify-start"
                      onClick={() => {
                        setPlace({ campusSlug: campus.slug, campusName: campus.name, locationId: l.id, locationName: l.name });
                        setOpen(false);
                      }}
                    >
                      {l.name}
                    </Button>
                  </li>
                ))}
            </ul>
          </div>
        )}
      </Modal>
    </>
  );
}
