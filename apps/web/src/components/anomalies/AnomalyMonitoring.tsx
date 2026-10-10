"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Database,
  Gauge,
  Percent,
  SlidersHorizontal,
} from "lucide-react";
import { getAnomalySummary, getEvaluationReport, getHealth } from "@/lib/api";
import type {
  AnomalySummary,
  EvaluationMetrics,
  EvaluationReport,
} from "@/types/anomaly";
import type { BackendStatus } from "@/types/monitoring";
import { formatDecimal, formatNumber, formatPercent } from "@/lib/format";
import DashboardHeader from "@/components/layout/DashboardHeader";
import StatCard from "@/components/dashboard/StatCard";
import ChartCard from "@/components/charts/ChartCard";
import SeverityDistributionChart from "@/components/anomalies/SeverityDistributionChart";
import AnomalyScoreDistributionChart from "@/components/anomalies/AnomalyScoreDistributionChart";
import AnomalyTable from "@/components/anomalies/AnomalyTable";
import {
  ChartSkeleton,
  ErrorState,
  KpiGridSkeleton,
} from "@/components/ui/Feedback";

const METRIC_ROWS: Array<{
  key: "precision" | "recall" | "f1_score" | "false_positive_rate" | "accuracy";
  label: string;
}> = [
  { key: "precision", label: "Precision" },
  { key: "recall", label: "Recall" },
  { key: "f1_score", label: "F1 score" },
  { key: "false_positive_rate", label: "False positive rate" },
  { key: "accuracy", label: "Accuracy" },
];

function MetricsTable({ metrics }: { metrics: EvaluationMetrics }) {
  return (
    <table className="w-full text-left text-xs">
      <caption className="sr-only">
        Detection metrics on the held-out test split
      </caption>
      <thead>
        <tr className="border-b border-line text-[11px] tracking-[0.1em] text-slate-500 uppercase">
          <th scope="col" className="py-2 pr-3 font-medium">
            Metric
          </th>
          <th scope="col" className="py-2 text-right font-medium">
            Value
          </th>
        </tr>
      </thead>
      <tbody>
        {METRIC_ROWS.map((row) => (
          <tr key={row.key} className="border-b border-line/60 last:border-b-0">
            <th scope="row" className="py-2 pr-3 font-normal text-slate-400">
              {row.label}
            </th>
            <td className="py-2 text-right font-medium text-slate-200 tabular-nums">
              {formatPercent(metrics[row.key])}
            </td>
          </tr>
        ))}
        <tr className="border-t border-line">
          <th scope="row" className="py-2 pr-3 font-normal text-slate-500">
            Confusion matrix
          </th>
          <td className="py-2 text-right text-[11px] text-slate-400 tabular-nums">
            TP {formatNumber(metrics.confusion_matrix.true_positive)} · FP{" "}
            {formatNumber(metrics.confusion_matrix.false_positive)} · FN{" "}
            {formatNumber(metrics.confusion_matrix.false_negative)} · TN{" "}
            {formatNumber(metrics.confusion_matrix.true_negative)}
          </td>
        </tr>
      </tbody>
    </table>
  );
}

export default function AnomalyMonitoring() {
  const [backendStatus, setBackendStatus] =
    useState<BackendStatus>("checking");
  const [summary, setSummary] = useState<AnomalySummary | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tableRefreshToken, setTableRefreshToken] = useState(0);

  async function fetchData() {
    return Promise.allSettled([
      getHealth(),
      getAnomalySummary(),
      getEvaluationReport(),
    ]);
  }

  const applyResults = useCallback(
    (results: Awaited<ReturnType<typeof fetchData>>) => {
      const [healthResult, summaryResult, evaluationResult] = results;

      if (healthResult.status === "fulfilled") {
        setBackendStatus(
          healthResult.value.status === "healthy" ? "connected" : "unavailable"
        );
      } else {
        setBackendStatus("unavailable");
      }

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
        setError(null);
      } else {
        const reason = summaryResult.reason;
        setError(
          reason instanceof Error
            ? reason.message
            : "Unable to load the anomaly summary."
        );
      }

      setEvaluation(
        evaluationResult.status === "fulfilled" ? evaluationResult.value : null
      );
      setLoading(false);
    },
    []
  );

  useEffect(() => {
    let stale = false;
    void fetchData().then((results) => {
      if (stale) return;
      applyResults(results);
    });
    return () => {
      stale = true;
    };
  }, [applyResults]);

  const handleRefresh = useCallback(() => {
    setBackendStatus("checking");
    setError(null);
    setRefreshing(true);
    void fetchData()
      .then((results) => {
        setLoading(false);
        applyResults(results);
      })
      .finally(() => setRefreshing(false));
    setTableRefreshToken((value) => value + 1);
  }, [applyResults]);

  const baselines = summary ? Object.entries(summary.feature_baselines) : [];

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader
        title="Anomaly Monitoring"
        subtitle="Unsupervised anomaly detection over AI4I 2020 sensor observations."
        datasetLabel="AI4I 2020 — Synthetic Dataset"
        backendStatus={backendStatus}
        onRefresh={handleRefresh}
        refreshing={refreshing}
      />

      <div className="flex-1 space-y-6 px-4 py-6 sm:px-6 xl:px-8">
        <section aria-labelledby="anomaly-stats-heading">
          <h2
            id="anomaly-stats-heading"
            className="mb-3 text-[11px] font-medium tracking-[0.14em] text-slate-500 uppercase"
          >
            Detection Overview
          </h2>

          {loading ? (
            <KpiGridSkeleton />
          ) : error && !summary ? (
            <div className="rounded-lg border border-line bg-surface">
              <ErrorState
                title="Anomaly summary unavailable"
                message={error}
                onRetry={handleRefresh}
              />
            </div>
          ) : summary ? (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard
                  label="Observations Analyzed"
                  value={formatNumber(summary.analyzed_sample_count)}
                  hint="Dataset samples scored by the detector"
                  icon={Database}
                  tone="accent"
                />
                <StatCard
                  label="Detected Anomalies"
                  value={formatNumber(summary.detected_anomaly_count)}
                  hint="Samples above the anomaly score threshold"
                  icon={AlertTriangle}
                  tone="danger"
                />
                <StatCard
                  label="Anomaly Rate"
                  value={formatPercent(summary.anomaly_rate)}
                  hint="Detected anomalies divided by samples analyzed"
                  icon={Percent}
                  tone="warning"
                />
                <StatCard
                  label="Anomaly Score Threshold"
                  value={formatDecimal(summary.threshold, 2)}
                  hint={`Feature z-score limit ${formatDecimal(
                    summary.feature_z_threshold,
                    2
                  )}`}
                  icon={Gauge}
                  tone="cyan"
                />
              </div>
              <p className="mt-3 flex items-start gap-2 text-[11px] leading-relaxed text-slate-500">
                <SlidersHorizontal
                  className="mt-0.5 h-3.5 w-3.5 shrink-0"
                  aria-hidden="true"
                />
                Algorithm {summary.algorithm}. Detected product is an
                application-defined anomaly level based on the robust z-score of
                each observation. It is not a calibrated failure probability and
                the dataset&apos;s ground-truth failure labels are never used as
                detection inputs.
              </p>
            </>
          ) : null}
        </section>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {loading ? (
            <>
              <ChartSkeleton />
              <ChartSkeleton />
            </>
          ) : summary ? (
            <>
              <ChartCard
                title="Severity Distribution"
                description="Detected anomalies grouped by application-defined severity level."
                note="Severity levels (low → critical) are defined by threshold multiples of the anomaly score and are specific to this application."
              >
                <SeverityDistributionChart
                  distribution={summary.severity_distribution}
                />
              </ChartCard>

              <ChartCard
                title="Anomaly Score Distribution"
                description="Histogram of anomaly scores across all analyzed observations."
                note="Bars at or above the configured threshold are marked as detected anomalies."
              >
                <AnomalyScoreDistributionChart
                  histogram={summary.score_histogram}
                  threshold={summary.threshold}
                />
              </ChartCard>
            </>
          ) : (
            <div className="rounded-lg border border-line bg-surface lg:col-span-2">
              <ErrorState
                title="Detection charts unavailable"
                message={
                  error ??
                  "The anomaly summary could not be loaded from the backend."
                }
                onRetry={handleRefresh}
              />
            </div>
          )}
        </div>

        {summary && (
          <ChartCard
            title="Feature Baselines"
            description="Robust baseline statistics per feature across the training split."
            note="Baselines use the median and median absolute deviation (MAD), making them resistant to outliers."
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-xs">
                <caption className="sr-only">
                  Feature baseline statistics used by the detector
                </caption>
                <thead>
                  <tr className="border-b border-line text-[11px] tracking-[0.1em] text-slate-500 uppercase">
                    <th scope="col" className="py-2 pr-3 font-medium">
                      Feature
                    </th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">
                      Median
                    </th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">
                      MAD
                    </th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">
                      Robust scale
                    </th>
                    <th scope="col" className="py-2 text-right font-medium">
                      Samples
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {baselines.map(([feature, stats]) => (
                    <tr
                      key={feature}
                      className="border-b border-line/60 last:border-b-0"
                    >
                      <th
                        scope="row"
                        className="py-2 pr-3 font-normal text-slate-300"
                      >
                        {feature}
                        {stats.degenerate && (
                          <span className="ml-2 rounded border border-warning/30 px-1.5 py-0.5 text-[10px] text-warning">
                            degenerate
                          </span>
                        )}
                      </th>
                      <td className="py-2 pr-3 text-right text-slate-300 tabular-nums">
                        {formatDecimal(stats.median, 2)}
                      </td>
                      <td className="py-2 pr-3 text-right text-slate-300 tabular-nums">
                        {formatDecimal(stats.mad, 2)}
                      </td>
                      <td className="py-2 pr-3 text-right text-slate-300 tabular-nums">
                        {formatDecimal(stats.scale, 3)}
                      </td>
                      <td className="py-2 text-right text-slate-400 tabular-nums">
                        {formatNumber(stats.count)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ChartCard>
        )}

        {evaluation && (
          <ChartCard
            title="Detection Evaluation"
            description="Agreement between detected anomalies and the dataset's ground-truth failure labels on the held-out test split."
            note="Ground-truth failure labels are used only for this retrospective evaluation. The threshold is selected on the validation split, never on the test split."
          >
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                <div>
                  <p className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
                    At configured threshold{" "}
                    {formatDecimal(evaluation.thresholds.configured, 2)}
                  </p>
                  <div className="mt-2">
                    <MetricsTable
                      metrics={evaluation.test_metrics_at_configured_threshold}
                    />
                  </div>
                </div>
                <div>
                  <p className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
                    At validation-tuned threshold{" "}
                    {formatDecimal(evaluation.thresholds.validation_tuned, 2)}
                  </p>
                  <div className="mt-2">
                    <MetricsTable
                      metrics={
                        evaluation.test_metrics_at_validation_tuned_threshold
                      }
                    />
                  </div>
                </div>
                <dl className="space-y-2 text-xs">
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Random seed</dt>
                    <dd className="text-slate-300 tabular-nums">
                      {evaluation.split.seed}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Train / Val / Test</dt>
                    <dd className="text-slate-300 tabular-nums">
                      {formatNumber(evaluation.split.train_count)} /{" "}
                      {formatNumber(evaluation.split.validation_count)} /{" "}
                      {formatNumber(evaluation.split.test_count)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Test failures</dt>
                    <dd className="text-slate-300 tabular-nums">
                      {formatNumber(
                        evaluation.test_class_balance.positive_failures
                      )}{" "}
                      of{" "}
                      {formatNumber(
                        evaluation.test_class_balance.positive_failures +
                          evaluation.test_class_balance.negative_failures
                      )}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Test failure rate</dt>
                    <dd className="text-slate-300 tabular-nums">
                      {formatPercent(evaluation.test_class_balance.failure_rate)}
                    </dd>
                  </div>
                </dl>
              </div>
              {evaluation.notes.length > 0 && (
                <ul className="space-y-1 border-t border-line pt-3 text-[11px] leading-relaxed text-slate-500">
                  {evaluation.notes.map((note, index) => (
                    <li key={index}>• {note}</li>
                  ))}
                </ul>
              )}
            </div>
          </ChartCard>
        )}

        <section aria-labelledby="anomaly-records-heading">
          <h2 id="anomaly-records-heading" className="sr-only">
            Anomaly records
          </h2>
          <AnomalyTable refreshToken={tableRefreshToken} />
        </section>

        <p className="pb-4 text-center text-[11px] text-slate-600">
          Detected anomalies are application-derived signals. Ground-truth
          failure labels are shown for comparison only and are never used as
          detector inputs.
        </p>
      </div>
    </div>
  );
}
