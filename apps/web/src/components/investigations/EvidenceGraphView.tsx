"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { Maximize2, Minus, Plus, RefreshCw, Share2 } from "lucide-react";
import { getEvidenceGraph } from "@/lib/api";
import type { EvidenceGraph, GraphNode } from "@/types/evidenceGraph";
import {
  GRAPH_NODE_COLORS,
  GRAPH_NODE_LABELS,
  GRAPH_RELATIONSHIP_COLORS,
  GRAPH_RELATIONSHIP_LABELS,
} from "@/lib/investigations";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/ui/Feedback";
import { cn } from "@/lib/format";

const NODE_W = 220;
const NODE_H = 62;
const PADDING_X = 140;
const PADDING_Y = 90;
const MIN_SCALE = 0.4;
const MAX_SCALE = 3;

const RELATIONSHIPS = [
  "SUPPORTS",
  "CONTRADICTS",
  "DERIVED_FROM",
  "RELATES_TO",
  "RECOMMENDS",
] as const;

function truncate(text: string, max = 34): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}\u2026`;
}

function boundaryPoint(
  cx: number,
  cy: number,
  tx: number,
  ty: number,
  halfW: number,
  halfH: number
): { x: number; y: number } {
  const dx = tx - cx;
  const dy = ty - cy;
  if (dx === 0 && dy === 0) return { x: cx, y: cy };
  const scale = Math.min(
    halfW / Math.max(Math.abs(dx), 1e-6),
    halfH / Math.max(Math.abs(dy), 1e-6)
  );
  return { x: cx + dx * scale, y: cy + dy * scale };
}

interface EvidenceGraphViewProps {
  investigationId: string;
}

export default function EvidenceGraphView({
  investigationId,
}: EvidenceGraphViewProps) {
  const [graph, setGraph] = useState<EvidenceGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<{ scale: number; tx: number; ty: number }>({
    scale: 1,
    tx: 0,
    ty: 0,
  });
  const dragStart = useRef<{ x: number; y: number; tx: number; ty: number } | null>(
    null
  );
  const svgRef = useRef<SVGSVGElement | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await getEvidenceGraph(investigationId);
      setGraph(next);
      setSelectedId((current) =>
        current && next.nodes.some((node) => node.id === current) ? current : null
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unexpected error while loading the graph."
      );
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  const bounds = useMemo(() => {
    if (!graph || graph.nodes.length === 0) return null;
    const xs = graph.nodes.map((node) => node.position.x);
    const ys = graph.nodes.map((node) => node.position.y);
    const minX = Math.min(...xs) - NODE_W / 2 - PADDING_X;
    const maxX = Math.max(...xs) + NODE_W / 2 + PADDING_X;
    const minY = Math.min(...ys) - NODE_H / 2 - PADDING_Y;
    const maxY = Math.max(...ys) + NODE_H / 2 + PADDING_Y;
    return { minX, minY, width: maxX - minX, height: maxY - minY };
  }, [graph]);

  const neighbors = useMemo(() => {
    if (!graph || !selectedId) return new Set<string>();
    const set = new Set<string>();
    for (const edge of graph.edges) {
      if (edge.source === selectedId) set.add(edge.target);
      if (edge.target === selectedId) set.add(edge.source);
    }
    return set;
  }, [graph, selectedId]);

  const selectedNode = useMemo(
    () => graph?.nodes.find((node) => node.id === selectedId) ?? null,
    [graph, selectedId]
  );

  const connectedEdges = useMemo(() => {
    if (!graph || !selectedId) return new Set<string>();
    return new Set(
      graph.edges
        .filter((edge) => edge.source === selectedId || edge.target === selectedId)
        .map((edge) => edge.id)
    );
  }, [graph, selectedId]);

  const zoomBy = useCallback((factor: number) => {
    setView((current) => {
      const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, current.scale * factor));
      if (scale === current.scale) return current;
      const ratio = scale / current.scale;
      return { scale, tx: current.tx * ratio, ty: current.ty * ratio };
    });
  }, []);

  const resetView = useCallback(() => setView({ scale: 1, tx: 0, ty: 0 }), []);

  if (loading && !graph) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <CardSkeleton />
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-lg border border-line bg-surface">
        <ErrorState
          title="Could not load evidence graph"
          message={error}
          onRetry={() => void load()}
        />
      </section>
    );
  }

  if (!graph || graph.nodes.length === 0 || !bounds) {
    return (
      <section className="rounded-lg border border-line bg-surface">
        <EmptyState
          title="No graph available"
          description="A completed investigation with evidence and hypotheses is required to draw the evidence graph."
        />
      </section>
    );
  }

  const isDimmed = (nodeId: string) =>
    !!selectedId && nodeId !== selectedId && !neighbors.has(nodeId);

  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-white">Evidence graph</h2>
          <p className="mt-1 text-xs text-slate-400">
            A deterministic projection of the evidence catalog, hypotheses and
            recommended actions. Drag to pan, click a node to inspect it.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void load()}
            aria-label="Reload graph"
            className="rounded-md border border-line bg-surface-raised p-2 text-slate-300 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => zoomBy(1.25)}
            aria-label="Zoom in"
            className="rounded-md border border-line bg-surface-raised p-2 text-slate-300 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => zoomBy(0.8)}
            aria-label="Zoom out"
            className="rounded-md border border-line bg-surface-raised p-2 text-slate-300 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
          >
            <Minus className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={resetView}
            aria-label="Reset view"
            className="rounded-md border border-line bg-surface-raised p-2 text-slate-300 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
          >
            <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-0 lg:flex-row">
        <div className="relative min-w-0 flex-1">
          <svg
            ref={svgRef}
            role="img"
            aria-label="Investigation evidence graph"
            viewBox={`${bounds.minX} ${bounds.minY} ${bounds.width} ${bounds.height}`}
            className="h-[520px] w-full touch-none cursor-grab select-none active:cursor-grabbing"
            onPointerDown={(event) => {
              svgRef.current?.setPointerCapture(event.pointerId);
              dragStart.current = { x: event.clientX, y: event.clientY, tx: view.tx, ty: view.ty };
            }}
            onPointerMove={(event) => {
              const start = dragStart.current;
              if (!start) return;
              setView((current) => ({
                ...current,
                tx: start.tx + (event.clientX - start.x),
                ty: start.ty + (event.clientY - start.y),
              }));
            }}
            onPointerUp={() => {
              dragStart.current = null;
            }}
          >
            <defs>
              {RELATIONSHIPS.map((relationship) => (
                <marker
                  key={relationship}
                  id={`arrow-${relationship}`}
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="7"
                  markerHeight="7"
                  orient="auto-start-reverse"
                >
                  <path
                    d="M 0 1 L 9 5 L 0 9 z"
                    fill={GRAPH_RELATIONSHIP_COLORS[relationship]}
                  />
                </marker>
              ))}
            </defs>

            <g transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
              {graph.edges.map((edge) => {
                const source = graph.nodes.find((node) => node.id === edge.source);
                const target = graph.nodes.find((node) => node.id === edge.target);
                if (!source || !target) return null;
                const highlighted =
                  !selectedId || connectedEdges.has(edge.id);
                const from = boundaryPoint(
                  source.position.x,
                  source.position.y,
                  target.position.x,
                  target.position.y,
                  NODE_W / 2,
                  NODE_H / 2
                );
                const to = boundaryPoint(
                  target.position.x,
                  target.position.y,
                  source.position.x,
                  source.position.y,
                  NODE_W / 2,
                  NODE_H / 2
                );
                return (
                  <g key={edge.id} pointerEvents="none">
                    <line
                      x1={from.x}
                      y1={from.y}
                      x2={to.x}
                      y2={to.y}
                      stroke={GRAPH_RELATIONSHIP_COLORS[edge.relationship]}
                      strokeWidth={highlighted ? 1.75 : 0.75}
                      strokeDasharray={edge.relationship === "CONTRADICTS" ? "6 4" : undefined}
                      strokeOpacity={highlighted ? 0.9 : 0.25}
                      markerEnd={`url(#arrow-${edge.relationship})`}
                    />
                    {highlighted && edge.label && (
                      <text
                        x={(from.x + to.x) / 2}
                        y={(from.y + to.y) / 2 - 6}
                        fontSize="11"
                        fill={GRAPH_RELATIONSHIP_COLORS[edge.relationship]}
                        opacity="0.85"
                        textAnchor="middle"
                      >
                        {edge.label}
                      </text>
                    )}
                  </g>
                );
              })}

              {graph.nodes.map((node) => {
                const color = GRAPH_NODE_COLORS[node.type];
                const dimmed = isDimmed(node.id);
                const isSelected = node.id === selectedId;
                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.position.x} ${node.position.y})`}
                    onClick={(event) => {
                      event.stopPropagation();
                      setSelectedId(isSelected ? null : node.id);
                    }}
                    className="cursor-pointer"
                  >
                    <title>
                      {`${GRAPH_NODE_LABELS[node.type]}\n${node.label}${
                        node.sublabel ? `\n${node.sublabel}` : ""
                      }`}
                    </title>
                    <rect
                      x={-NODE_W / 2}
                      y={-NODE_H / 2}
                      width={NODE_W}
                      height={NODE_H}
                      rx="10"
                      fill="#16213a"
                      stroke={color}
                      strokeWidth={isSelected ? 2.5 : 1.25}
                      strokeOpacity={dimmed ? 0.35 : 1}
                      opacity={dimmed ? 0.4 : 1}
                    />
                    <rect
                      x={-NODE_W / 2}
                      y={-NODE_H / 2}
                      width="5"
                      height={NODE_H}
                      rx="2.5"
                      fill={color}
                      opacity={dimmed ? 0.35 : 1}
                    />
                    <text
                      x={-NODE_W / 2 + 16}
                      y={-8}
                      fontSize="12"
                      fontWeight="600"
                      fill="#e2e8f0"
                      opacity={dimmed ? 0.4 : 1}
                    >
                      {truncate(node.label)}
                    </text>
                    <text
                      x={-NODE_W / 2 + 16}
                      y={12}
                      fontSize="10.5"
                      fill="#94a3b8"
                      opacity={dimmed ? 0.4 : 1}
                    >
                      {truncate(node.sublabel ?? GRAPH_NODE_LABELS[node.type], 40)}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>

          <div className="pointer-events-none absolute top-3 left-3 flex flex-wrap gap-x-4 gap-y-1 rounded-md border border-line/60 bg-surface/90 px-3 py-2 backdrop-blur">
            {RELATIONSHIPS.map((relationship) => (
              <span key={relationship} className="inline-flex items-center gap-1.5 text-[10px] text-slate-400">
                <span
                  className="h-2 w-2 rounded-sm"
                  style={{ backgroundColor: GRAPH_RELATIONSHIP_COLORS[relationship] }}
                  aria-hidden="true"
                />
                {GRAPH_RELATIONSHIP_LABELS[relationship]}
              </span>
            ))}
          </div>

          <p className="absolute bottom-3 left-3 rounded border border-line/60 bg-surface/90 px-2 py-1 text-[10px] text-slate-500 backdrop-blur">
            {graph.node_count} nodes · {graph.edge_count} edges
          </p>
        </div>

        {selectedNode ? (
          <NodeDetailPanel node={selectedNode} />
        ) : (
          <aside className="hidden w-80 shrink-0 border-l border-line p-5 lg:block">
            <div className="flex items-center gap-2 text-slate-400">
              <Share2 className="h-4 w-4 text-cyan-accent" aria-hidden="true" />
              <p className="text-xs">Select a node to inspect its supporting records.</p>
            </div>
          </aside>
        )}
      </div>
    </section>
  );
}

function NodeDetailPanel({ node }: { node: GraphNode }) {
  const rows = node.data;
  const primary = [
    ["Type", GRAPH_NODE_LABELS[node.type]],
    ["Evidence ID", rows.evidence_id as string | undefined],
    ["Evidence type", rows.evidence_type as string | undefined],
    ["Assessment", rows.assessment as string | undefined],
    ["Source", rows.source as string | undefined],
    ["Value", rows.value as string | undefined],
    ["Observation", (rows.observation ?? rows.visible_observation ?? rows.passage) as string | undefined],
    ["Measurement", rows.measurement as string | undefined],
    ["Robust z-score", rows.robust_zscore as number | undefined],
    ["Document", rows.document_title as string | undefined],
    ["Anomaly score", rows.anomaly_score as number | undefined],
    ["Severity", rows.severity as string | undefined],
    ["Direction", rows.direction as string | undefined],
    ["Provenance", rows.provenance as string | undefined],
  ].filter((entry): entry is [string, string | number] => entry[1] !== null && entry[1] !== undefined);

  return (
    <aside className="max-h-[520px] w-full shrink-0 overflow-y-auto border-t border-line p-5 lg:w-80 lg:border-t-0 lg:border-l">
      <div className="flex items-center gap-2">
        <span
          className="h-2.5 w-2.5 rounded-sm"
          style={{ backgroundColor: GRAPH_NODE_COLORS[node.type] }}
          aria-hidden="true"
        />
        <h3 className="text-xs font-semibold text-white">{GRAPH_NODE_LABELS[node.type]}</h3>
      </div>
      <p className="mt-1 break-words font-mono text-[11px] text-cyan-accent">{node.id}</p>

      <dl className="mt-3 space-y-2.5">
        {primary.map(([label, value]) => (
          <div key={label}>
            <dt className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">{label}</dt>
            <dd
              className={cn(
                "mt-0.5 text-[11px] leading-relaxed text-slate-300",
                typeof value === "number" && "font-mono tabular-nums"
              )}
            >
              {String(value)}
            </dd>
          </div>
        ))}
      </dl>

      {typeof rows.contradicting_evidence_ids === "object" && rows.contradicting_evidence_ids && (rows.contradicting_evidence_ids as unknown[]).length > 0 && (
        <ListGroup title="Contradicting evidence" items={rows.contradicting_evidence_ids as string[]} mono />
      )}
      {typeof rows.missing_evidence === "object" && rows.missing_evidence && (rows.missing_evidence as unknown[]).length > 0 && (
        <ListGroup title="Missing evidence" items={rows.missing_evidence as string[]} />
      )}
      {typeof rows.verification_steps === "object" && rows.verification_steps && (rows.verification_steps as unknown[]).length > 0 && (
        <ListGroup title="Verification steps" items={rows.verification_steps as string[]} />
      )}
      {typeof rows.observations === "object" && Array.isArray(rows.observations) && rows.observations.length > 0 && (
        <ListGroup
          title="Vision observations"
          items={(rows.observations as Array<{ observation: string }>).map((item) => item.observation)}
        />
      )}
      {typeof rows.limitations === "object" && Array.isArray(rows.limitations) && rows.limitations.length > 0 && (
        <ListGroup title="Vision limitations" items={rows.limitations as string[]} />
      )}
    </aside>
  );
}

function ListGroup({ title, items, mono = false }: { title: string; items: string[]; mono?: boolean }) {
  return (
    <div className="mt-4">
      <p className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">{title}</p>
      <ul className="mt-1.5 space-y-1">
        {items.map((item, index) => (
          <li key={`${item}-${index}`} className="rounded border border-line bg-surface-raised px-2 py-1.5 text-[11px] leading-relaxed text-slate-400">
            <span className={mono ? "font-mono" : undefined}>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}