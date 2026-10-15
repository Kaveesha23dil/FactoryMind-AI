"use client";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { SlidersHorizontal, Sparkles, Activity, Bell, Database, ShieldCheck, Info, LockKeyhole, RefreshCw, Copy } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { DEFAULT_PREFERENCES, PREFERENCE_EVENT, formatTimestamp, readPreferences, savePreferences, validatePreferences, type Preferences } from "@/lib/preferences";
import type { SettingsInfo, SystemInfo } from "@/types/settings";
import packageInfo from "../../../package.json";
import "./settings.css";

const sections = [
 { name: "General", icon: SlidersHorizontal, description: "Make FactoryMind feel like your workspace." },
 { name: "AI Configuration", icon: Sparkles, description: "Investigation limits and provider availability." },
 { name: "Anomaly Detection", icon: Activity, description: "Inspect the deterministic detection baseline." },
 { name: "Notifications", icon: Bell, description: "Delivery capabilities and supported alerts." },
 { name: "Data Management", icon: Database, description: "Know where your evidence and records come from." },
 { name: "Security & Access", icon: ShieldCheck, description: "Authentication and access controls, clearly explained." },
 { name: "System Information", icon: Info, description: "Safe diagnostics without consuming Gemini quota." },
];
function SettingsCard({ title, description, children }: Readonly<{ title: string; description?: string; children: ReactNode }>) {
 return <section className="settings-card"><div className="settings-card-heading"><h3>{title}</h3>{description && <p>{description}</p>}</div>{children}</section>;
}
function SettingsField({ label, children }: Readonly<{ label: string; children: ReactNode }>) {
 return <div className="settings-row"><span>{label}</span><div>{children}</div></div>;
}
function display(value: string | number | boolean | null | undefined) {
 if (value == null) return "Not recorded / unavailable";
 if (typeof value === "boolean") return value ? "Enabled" : "Disabled";
 return String(value);
}
function severityBand(lower: number | null, upper: number | null) {
 const end = upper == null ? "" : ` < ${upper}`;
 return `${lower} ≤ score${end}`;
}
function ReadOnly({ values }: Readonly<{ values: Record<string, string | number | boolean | null | undefined> }>) {
 return <div>{Object.entries(values).map(([label, value]) => <SettingsField key={label} label={label}><span className="settings-value">{display(value)}</span></SettingsField>)}</div>;
}
function ToggleSetting({ label }: Readonly<{ label: string }>) {
 return <div className="settings-row"><span>{label}<small>Delivery not configured</small></span><input type="checkbox" role="switch" aria-label={label} disabled /></div>;
}
export default function SettingsDashboard() {
 const [active, setActive] = useState(0);
 const [data, setData] = useState<SettingsInfo | null>(null);
 const [system, setSystem] = useState<SystemInfo | null>(null);
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState("");
 const [systemError, setSystemError] = useState("");
 const [checking, setChecking] = useState(false);
 const [saved, setSaved] = useState<Preferences>(DEFAULT_PREFERENCES);
 const [draft, setDraft] = useState<Preferences>(DEFAULT_PREFERENCES);
 const [feedback, setFeedback] = useState("");
 const [saveError, setSaveError] = useState("");
 const dirty = JSON.stringify(saved) !== JSON.stringify(draft);
 async function refreshMetadata() {
  setLoading(true); setError("");
  try { setData(await apiFetch<SettingsInfo>("/api/settings")); }
  catch { setError("Settings could not be loaded. Check backend connectivity and access, then retry."); }
  finally { setLoading(false); }
 }
 async function refreshSystem() {
  setChecking(true); setSystemError("");
  try { setSystem(await apiFetch<SystemInfo>("/api/settings/system")); }
  catch { setSystemError("System status is unavailable. The backend may be offline or access may be denied."); setSystem(null); }
  finally { setChecking(false); }
 }
 useEffect(() => {
  const timer = setTimeout(() => {
   const prefs = readPreferences(); setSaved(prefs); setDraft(prefs);
   void refreshMetadata(); void refreshSystem();
  }, 0);
  return () => clearTimeout(timer);
 }, []);
 useEffect(() => {
  if (!dirty) return;
  const unload = (event: BeforeUnloadEvent) => { event.preventDefault(); };
  const navigate = (event: MouseEvent) => {
   const target = event.target instanceof Element ? event.target.closest("a[href]") : null;
   if (!(target instanceof HTMLAnchorElement) || target.target === "_blank" || target.href === location.href) return;
   if (!window.confirm("You have unsaved preferences. Leave without saving?")) { event.preventDefault(); event.stopPropagation(); }
  };
  window.addEventListener("beforeunload", unload); document.addEventListener("click", navigate, true);
  return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigate, true); };
 }, [dirty]);
 useEffect(() => {
  const sync = () => { if (!dirty) { const next = readPreferences(); setSaved(next); setDraft(next); } };
  window.addEventListener("storage", sync); window.addEventListener(PREFERENCE_EVENT, sync);
  return () => { window.removeEventListener("storage", sync); window.removeEventListener(PREFERENCE_EVENT, sync); };
 }, [dirty]);
 const update = <K extends keyof Preferences>(key: K, value: Preferences[K]) => { setDraft(current => ({ ...current, [key]: value })); setFeedback(""); setSaveError(""); };
 const timestamp = (value: string | null | undefined) => value ? formatTimestamp(value, saved) : null;
 function save() {
  setFeedback(""); setSaveError("");
  try { savePreferences(draft); setSaved({ ...draft }); setFeedback("Preferences saved in this browser."); }
  catch (reason) { setSaveError(reason instanceof Error ? reason.message : "Preferences could not be saved. Check browser storage permissions."); }
 }
 async function copyDiagnostics() {
  try {
   if (!system) return;
   await navigator.clipboard.writeText(JSON.stringify({ frontend_package_version: packageInfo.version, frontend_build: "Not recorded", ...system }, null, 2));
   setFeedback("Safe diagnostic summary copied.");
  } catch { setSaveError("Clipboard access failed. Check your browser permissions."); }
 }
 const section = sections[active];
 let geminiConfiguration = "Unknown";
 if (data) geminiConfiguration = data.ai.credentials_configured ? "Credentials configured; connectivity not probed" : "Credentials not configured";
 return <div className="settings-page">
  <header className="settings-header"><div className="settings-eyebrow">WORKSPACE / SETTINGS</div><h1>Workspace settings<span>.</span></h1><p>Your preferences, platform configuration and system health in one place.</p></header>
  <div className="settings-layout">
   <aside className="settings-sidebar"><nav aria-label="Settings categories">{sections.map(({ name, icon: Icon }, index) => <button key={name} type="button" aria-current={active === index ? "page" : undefined} onClick={() => { setActive(index); setFeedback(""); setSaveError(""); }}><Icon size={17} aria-hidden="true" />{name}</button>)}</nav><p><LockKeyhole size={15} />Operational configuration is managed by your deployment administrator.</p></aside>
   <div className="settings-content"><div className="settings-section-heading"><div><h2>{section.name}</h2><p>{section.description}</p></div><span className="settings-badge">{active === 0 ? "Personal preferences" : "System visibility"}</span></div>
    {dirty && <div className="settings-notice" role="status">You have unsaved preferences in General.</div>}
    {feedback && <div className="settings-notice" role="status">{feedback}</div>}
    {saveError && <div className="settings-error" role="alert">{saveError}</div>}
    {loading && <div className="settings-skeleton" role="status" aria-label="Loading settings">Loading workspace configuration…</div>}
    {error && <div className="settings-error" role="alert">{error} <button onClick={refreshMetadata}>Retry</button></div>}
    {active === 0 && <>
     {data && <SettingsCard title="Workspace information" description="Read-only workspace identity."><ReadOnly values={{ "Workspace name": data.workspace.workspace, Application: data.workspace.application, Team: data.workspace.team, Environment: data.workspace.environment }} /></SettingsCard>}
     <SettingsCard title="Appearance" description="Saved locally for this browser and origin. No account synchronization.">
      <SettingsField label="Color theme"><select aria-label="Color theme" value={draft.appearance} onChange={event => update("appearance", event.target.value as Preferences["appearance"])}><option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option></select></SettingsField>
      <SettingsField label="Display density"><select aria-label="Display density" value={draft.density} onChange={event => update("density", event.target.value as Preferences["density"])}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></SettingsField>
     </SettingsCard>
     <SettingsCard title="Regional preferences" description="Applies to formatted application timestamps. Dataset row indices are never treated as time.">
      <SettingsField label="Date format"><select aria-label="Date format" value={draft.dateFormat} onChange={event => update("dateFormat", event.target.value as Preferences["dateFormat"])}><option value="medium">Jan 31, 2026</option><option value="iso">2026-01-31</option><option value="day-first">31/01/2026</option></select></SettingsField>
      <SettingsField label="Time format"><select aria-label="Time format" value={draft.timeFormat} onChange={event => update("timeFormat", event.target.value as Preferences["timeFormat"])}><option value="12h">12-hour</option><option value="24h">24-hour</option></select></SettingsField>
      <SettingsField label="Timezone"><label><span className="sr-only">Timezone</span><input aria-label="Timezone" aria-describedby="timezone-help" aria-invalid={!validatePreferences(draft)} value={draft.timeZone} onChange={event => update("timeZone", event.target.value)} /><small id="timezone-help">Use “system” or an IANA zone, e.g. Asia/Colombo.</small>{!validatePreferences(draft) && <small className="settings-validation">Enter a valid IANA timezone.</small>}</label></SettingsField>
      <ReadOnly values={{ "Measurement units (fixed)": "K · rpm · N·m · W · min" }} /><p className="settings-footnote">Unit conversion is not available. Sensor calculations retain their documented units.</p>
     </SettingsCard>
     <div className="settings-actions"><span>{dirty ? "Changes apply after saving" : "All preferences saved"}</span><button disabled={!dirty} onClick={() => { setDraft({ ...saved }); setSaveError(""); setFeedback(""); }}>Reset changes</button><button className="settings-save" disabled={!dirty || !validatePreferences(draft)} onClick={save}>Save changes</button></div>
    </>}
    {active === 1 && data && <>
     <SettingsCard title="Investigation runtime" description="Read-only deployment configuration. Changes require an administrator and service restart."><ReadOnly values={{ Provider: data.ai.provider, "Configured model": data.ai.model, "AI investigations": data.ai.enabled, "Provider credentials configured": data.ai.credentials_configured ? "Yes (values never exposed)" : "No", "Timeout (seconds)": data.ai.timeout_seconds, "Maximum application retries": data.ai.max_retries, "Concurrent model requests per process": data.ai.max_concurrent_requests, "Concurrent investigations": data.ai.max_concurrent_investigations, "Maximum model calls per agent": data.ai.max_model_calls_per_agent, "Investigation report cache": data.ai.cache_enabled }} /></SettingsCard>
     <SettingsCard title="Usage & provider status" description={data.ai.usage.scope}><ReadOnly values={{ "Recorded requests": data.ai.usage.requests, "Recorded input tokens": data.ai.usage.input_tokens, "Recorded output tokens": data.ai.usage.output_tokens, "Latest recorded investigation error category": data.ai.latest_error_category, "Provider cooldown until": timestamp(data.ai.cooldown_until), "Last completed investigation": timestamp(data.ai.last_success_at) }} /><p className="settings-footnote">Provider quota and remaining allowance are unavailable. No Gemini requests are sent by this page. SDK retries may be additional to application retries.</p></SettingsCard>
    </>}
    {active === 2 && data && <>
     <SettingsCard title="Detection baseline" description="Read-only deterministic configuration. Historical incidents are preserved."><ReadOnly values={{ "Algorithm / version": data.anomaly.algorithm, "Anomaly score threshold (dimensionless)": data.anomaly.threshold, "Feature robust z-score threshold": data.anomaly.feature_z_threshold, "Baseline dataset": data.data.name, "Training / validation / test records": `${data.anomaly.train_count} / ${data.anomaly.validation_count} / ${data.anomaly.test_count}`, "Split seed": data.anomaly.split_seed, "Last evaluation date": timestamp(data.anomaly.last_evaluation_at) }} /></SettingsCard>
     <SettingsCard title="Severity bands" description="Application-defined multiples of the anomaly threshold, not failure probabilities."><ReadOnly values={Object.fromEntries(Object.entries(data.anomaly.severity_bands).map(([level, [lower, upper]]) => [level, severityBand(lower, upper)]))} /><p className="settings-footnote">Threshold editing and audit-backed reconfiguration are not supported. Ground-truth failure labels are evaluation-only.</p></SettingsCard>
    </>}
    {active === 3 && <SettingsCard title="Notification delivery" description="Notification subscriptions and delivery providers are not implemented. These controls are unavailable.">{["High-severity incidents", "Investigation completed", "Investigation failed", "Counterfactual analysis completed", "Gemini quota errors", "System service failures"].map(label => <ToggleSetting key={label} label={label} />)}<ReadOnly values={{ "In-app subscriptions": "Unavailable", Email: "Unavailable", SMS: "Unavailable", Push: "Unavailable" }} /></SettingsCard>}
    {active === 4 && data && <>
     <SettingsCard title="Active dataset" description="AI4I 2020 is a synthetic predictive maintenance dataset. Records do not represent continuous live telemetry from a physical machine."><ReadOnly values={{ Dataset: data.data.name, Origin: data.data.origin, Classification: data.data.classification, "Analyzed records": data.data.records, "Content SHA-256 (first 12 characters)": data.data.version, "Last refresh": timestamp(data.data.last_refresh_at) }} /></SettingsCard>
     <SettingsCard title="Evidence & storage"><ReadOnly values={{ Database: data.data.database_provider, "Image storage provider": data.data.image_provider, "Reference documents": data.data.document_count, "Indexed passages": data.data.passage_count, "Document collection": data.data.document_status, "Storage usage (bytes)": data.data.storage_usage_bytes, "Automated backup": "Not configured by this application" }} /><p className="settings-footnote">Uploaded maintenance-document indexing is not implemented. Packaged references are not real factory records.</p><div className="settings-inline-actions"><button disabled={loading} onClick={refreshMetadata}><RefreshCw size={14} />Refresh metadata</button><Link href="/investigations">Open reports to review & export →</Link></div></SettingsCard>
    </>}
    {active === 5 && data && <SettingsCard title="Access & authentication" description="Read-only security visibility; no credentials or private deployment identifiers are returned."><ReadOnly values={{ Authentication: data.security.authentication, "Current end-user role": data.security.role, Environment: data.workspace.environment, Session: data.security.session, "Access management": data.security.access_management, "Operational settings": data.security.operational_settings, "Audit records": "Not available through Settings" }} /><p className="settings-footnote">Production requests use existing verified Google service identity controls. This is not an end-user login or role-management system.</p></SettingsCard>}
    {active === 6 && <SettingsCard title="Service diagnostics" description="Connectivity is checked on request. Unknown means a service has not been verified.">{systemError && <p role="alert" className="settings-error">{systemError}</p>}<ReadOnly values={{ "Frontend package version": packageInfo.version, "Frontend build version": "Not recorded", "Application / backend API version": system?.application_version, "Backend connectivity": system?.api_status ?? "Unknown", "Database connectivity": system?.database_status ?? "Unknown", "Image storage connectivity": system?.image_storage_status ?? "Unknown", "Gemini health": system?.gemini_status ?? "Unknown", "Gemini configuration": geminiConfiguration, "Storage provider": data?.data.image_provider, Environment: system?.environment, "Checked at": timestamp(system?.checked_at) }} /><div className="settings-inline-actions"><button disabled={checking} onClick={refreshSystem}><RefreshCw size={14} />{checking ? "Checking…" : "Refresh status"}</button><button disabled={!system || checking} onClick={copyDiagnostics}><Copy size={14} />Copy diagnostic summary</button></div></SettingsCard>}
   </div>
  </div><footer className="settings-footer">FactoryMind AI <span>Evidence-driven intelligence · AetherForge</span></footer>
 </div>;
}

