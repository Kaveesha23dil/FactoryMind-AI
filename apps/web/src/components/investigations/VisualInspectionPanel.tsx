"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  ScanSearch,
  ShieldQuestion,
  Upload,
} from "lucide-react";
import {
  analyzeImage,
  getIncidentImages,
  imageContentUrl,
  uploadIncidentImage,
} from "@/lib/api";
import type {
  VisualEvidenceListResponse,
  VisualEvidenceRecord,
} from "@/types/visual";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  CardSkeleton,
  EmptyState,
  ErrorState,
} from "@/components/ui/Feedback";
import {
  SEVERITY_HINT_LABELS,
  SEVERITY_HINT_TONE,
  VISUAL_STATUS_LABELS,
  VISUAL_STATUS_TONE,
} from "@/lib/investigations";
import { cn, formatDateTime } from "@/lib/format";

const MAX_BYTES = 5 * 1024 * 1024;

interface VisualInspectionPanelProps {
  incidentId: string;
  investigationId: string;
}

export default function VisualInspectionPanel({
  incidentId,
  investigationId,
}: VisualInspectionPanelProps) {
  const [list, setList] = useState<VisualEvidenceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let stale = false;
    (async () => {
      try {
        const next = await getIncidentImages(incidentId);
        if (stale) return;
        setList(next);
        setError(null);
        setSelectedId((current) => {
          if (current && next.items.some((item) => item.image_id === current)) {
            return current;
          }
          return next.items[0]?.image_id ?? null;
        });
      } catch (err) {
        if (stale) return;
        setError(
          err instanceof Error ? err.message : "Unexpected error while loading images."
        );
      } finally {
        if (!stale) setLoading(false);
      }
    })();
    return () => {
      stale = true;
    };
  }, [incidentId, tick]);

  const refresh = useCallback(() => setTick((value) => value + 1), []);

  const selected = list?.items.find((item) => item.image_id === selectedId) ?? null;

  const onUpload = async (file: File) => {
    setActionError(null);
    if (file.size > MAX_BYTES) {
      setActionError("Image is larger than the 5 MB upload limit.");
      return;
    }
    setUploading(true);
    try {
      const created = await uploadIncidentImage(incidentId, file);
      setSelectedId(created.image_id);
      refresh();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "The image could not be uploaded."
      );
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const onAnalyze = async () => {
    if (!selected) return;
    setAnalyzing(true);
    setActionError(null);
    try {
      const updated = await analyzeImage(selected.image_id, investigationId);
      setList((current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) =>
                item.image_id === updated.image_id ? updated : item
              ),
            }
          : current
      );
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "The image could not be analyzed."
      );
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,480px)]">
      <section className="rounded-lg border border-line bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-white">Inspection images</h2>
            <p className="mt-1 text-xs text-slate-400">
              Upload machine photos. The vision agent describes what is visible and
              records limitations; it never confirms a physical diagnosis.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={refresh}
              aria-label="Refresh images"
              className="rounded-md border border-line bg-surface-raised p-2 text-slate-300 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-accent/90 focus-visible:ring-2 focus-visible:ring-cyan-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            >
              {uploading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <Upload className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              {uploading ? "Uploading…" : "Upload image"}
            </button>
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void onUpload(file);
              }}
            />
          </div>
        </div>

        {actionError && (
          <p className="flex items-start gap-1.5 border-b border-line px-5 py-2.5 text-[11px] text-danger">
            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
            {actionError}
          </p>
        )}

        {loading && !list ? (
          <div className="p-5">
            <CardSkeleton />
          </div>
        ) : error ? (
          <ErrorState title="Could not load images" message={error} onRetry={refresh} />
        ) : !list || list.items.length === 0 ? (
          <EmptyState
            title="No inspection images"
            description="Upload a PNG, JPEG, GIF, or WEBP image to begin a visual inspection."
            icon={ImageIcon}
          />
        ) : (
          <ul className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2 lg:grid-cols-3">
            {list.items.map((item) => (
              <li key={item.image_id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(item.image_id)}
                  className={cn(
                    "flex w-full flex-col overflow-hidden rounded-md border text-left transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none",
                    item.image_id === selectedId
                      ? "border-cyan-accent/60 bg-surface-raised"
                      : "border-line bg-surface-raised/50 hover:bg-surface-raised"
                  )}
                >
                  <span className="block aspect-video w-full overflow-hidden bg-background">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={imageContentUrl(item.image_id)}
                      alt={item.filename}
                      className="h-full w-full object-cover"
                    />
                  </span>
                  <span className="flex flex-col gap-1.5 p-3">
                    <span className="truncate text-[11px] font-medium text-slate-200">
                      {item.filename}
                    </span>
                    <span className="flex items-center gap-2">
                      <StatusBadge
                        label={VISUAL_STATUS_LABELS[item.status]}
                        tone={VISUAL_STATUS_TONE[item.status]}
                        dot
                      />
                      <span className="text-[10px] text-slate-500">
                        {item.width && item.height ? `${item.width}×${item.height}` : "—"}
                      </span>
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {selected ? (
        <VisualDetail
          image={selected}
          analyzing={analyzing}
          onAnalyze={() => void onAnalyze()}
        />
      ) : (
        <section className="rounded-lg border border-dashed border-line bg-surface">
          <EmptyState
            title="No image selected"
            description="Select an inspection image to review or analyze it."
            icon={ImageIcon}
          />
        </section>
      )}
    </div>
  );
}

function VisualDetail({
  image,
  analyzing,
  onAnalyze,
}: {
  image: VisualEvidenceRecord;
  analyzing: boolean;
  onAnalyze: () => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="overflow-hidden rounded-t-lg border-b border-line bg-background">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageContentUrl(image.image_id)}
          alt={image.filename}
          className="mx-auto max-h-80 w-full object-contain"
        />
      </div>

      <div className="space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold text-white">{image.filename}</p>
            <p className="mt-0.5 font-mono text-[10px] text-slate-500">{image.image_id}</p>
          </div>
          <StatusBadge
            label={VISUAL_STATUS_LABELS[image.status]}
            tone={VISUAL_STATUS_TONE[image.status]}
            dot
          />
        </div>

        <dl className="grid grid-cols-2 gap-3 text-[11px]">
          <Detail label="Type" value={image.mime_type} />
          <Detail
            label="Size"
            value={`${(image.size_bytes / 1024).toFixed(1)} KB`}
          />
          <Detail
            label="Dimensions"
            value={image.width && image.height ? `${image.width}×${image.height}` : "unknown"}
          />
          <Detail label="Uploaded" value={formatDateTime(image.created_at)} />
        </dl>

        <button
          type="button"
          onClick={onAnalyze}
          disabled={analyzing}
          className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-accent px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-accent/90 focus-visible:ring-2 focus-visible:ring-cyan-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
        >
          {analyzing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <ScanSearch className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {analyzing
            ? "Analyzing…"
            : image.status === "analyzed"
              ? "Re-analyze image"
              : "Analyze image"}
        </button>

        {image.status === "failed" && image.error && (
          <div className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-[11px] text-danger">
            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
            <span className="break-words">{image.error}</span>
          </div>
        )}

        {image.summary && (
          <div>
            <p className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">
              Visible summary
            </p>
            <p className="mt-1 text-xs leading-relaxed text-slate-300">{image.summary}</p>
          </div>
        )}

        {image.observations.length > 0 && (
          <div>
            <p className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">
              Observations
            </p>
            <ul className="mt-1.5 space-y-1.5">
              {image.observations.map((observation, index) => (
                <li
                  key={`${observation.observation}-${index}`}
                  className="rounded border border-line bg-surface-raised px-2.5 py-2 text-[11px]"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="leading-relaxed text-slate-300">{observation.observation}</p>
                    <StatusBadge
                      label={SEVERITY_HINT_LABELS[observation.severity_hint]}
                      tone={SEVERITY_HINT_TONE[observation.severity_hint]}
                    />
                  </div>
                  {observation.related_features.length > 0 && (
                    <p className="mt-1 font-mono text-[10px] text-slate-500">
                      {observation.related_features.join(", ")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {image.limitations.length > 0 && (
          <div className="rounded-md border border-warning/30 bg-warning/5 px-3 py-2.5">
            <p className="flex items-center gap-1.5 text-[10px] font-medium tracking-wide text-warning uppercase">
              <ShieldQuestion className="h-3 w-3" aria-hidden="true" />
              Limitations
            </p>
            <ul className="mt-1 space-y-0.5">
              {image.limitations.map((item, index) => (
                <li key={`${item}-${index}`} className="text-[11px] leading-relaxed text-slate-300">
                  · {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-[10px] leading-relaxed text-slate-600">{image.provenance}</p>
      </div>
    </section>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">{label}</dt>
      <dd className="mt-0.5 break-words text-slate-300">{value}</dd>
    </div>
  );
}