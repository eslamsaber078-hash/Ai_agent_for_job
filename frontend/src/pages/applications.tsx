import { useEffect, useRef, useState } from "react";
import { Bot, ExternalLink, ListChecks, Pencil, Plus, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api, AI_TIMEOUT, qs } from "@/lib/api";
import { APP_STATUSES, type Application, type Job, type PreparedApplication } from "@/lib/types";
import { formatDate, toInputDate } from "@/lib/format";
import { Button, buttonClassName } from "@/components/ui/button";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge, STATUS_OPTIONS } from "@/components/jobs/status-badge";
import { ApplyRouteTag } from "@/components/applications/apply-route";
import { PackDialog, PackRow, type Pack } from "@/components/applications/pack-dialog";
import { PageHeader } from "@/components/layout/page-header";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";

const COLUMNS = ["Discovered", "Interested", "Preparing", "Applied", "Interview", "Offer", "Rejected", "Archived"];

export function ApplicationsPage() {
  const { toast } = useToast();
  const { t } = useI18n();
  const [items, setItems] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The table needs 1080px to stay readable; on a phone the board is the honest default.
  const [view, setView] = useState<"table" | "kanban">(() =>
    window.innerWidth < 768 ? "kanban" : "table"
  );
  const [statusFilter, setStatusFilter] = useState("");
  const [editing, setEditing] = useState<Application | null>(null);
  const [deleting, setDeleting] = useState<Application | null>(null);
  const [pack, setPack] = useState<Pack | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const reqId = useRef(0);
  const packId = useRef(0);

  const load = () => {
    const my = ++reqId.current;
    setError(null);
    // Keep the rows already on screen while the fetch runs — clearing them first
    // made every status change flash a skeleton over the whole table. The reqId
    // guard drops a stale response, so the new filter's rows replace the old ones.
    api
      .get<Application[]>(`/api/applications${qs({ status: statusFilter })}`)
      .then((d) => { if (my === reqId.current) setItems(d); })
      .catch((e) => { if (my === reqId.current) setError(e.message); });
  };

  useEffect(load, [statusFilter]);

  /** One click, five documents — and the route the ad itself named. Nothing is sent. */
  const prepare = async (app: Application) => {
    const my = ++packId.current;
    setBusyId(app.id);
    try {
      const res = await api.post<PreparedApplication>("/api/applications/prepare", {
        job_id: app.job.id,
        notes: app.notes || "",
      }, { timeout: AI_TIMEOUT });
      if (my !== packId.current) return;
      setPack({ job: res.application.job, applicationId: res.application.id, materials: res.materials });
      toast(t("Prepared {n} documents for this ad", { n: res.materials.length }));
      load();
    } catch (e: any) {
      if (my === packId.current) toast(e.message, "error");
    } finally {
      if (my === packId.current) setBusyId(null);
    }
  };

  const openPack = async (app: Application) => {
    const my = ++packId.current;
    setBusyId(app.id);
    try {
      const materials = await api.get<Pack["materials"]>(`/api/applications/${app.id}/materials`);
      if (my !== packId.current) return;
      setPack({ job: app.job, applicationId: app.id, materials });
    } catch (e: any) {
      if (my === packId.current) toast(e.message, "error");
    } finally {
      if (my === packId.current) setBusyId(null);
    }
  };

  /** Opening the ad from inside the pack counts as applying. The row moves to Applied
   *  and the pack stays open with the posting's new stage, so nothing he is reading
   *  vanishes under him. */
  const markFromPack = (job: Job) => {
    api
      .post<Job>(`/api/jobs/${job.id}/applied`)
      .then((fresh) => {
        setPack((p) => (p && p.job.id === fresh.id ? { ...p, job: fresh } : p));
        toast(t("Marked as applied"));
        load();
      })
      .catch((e: any) => toast(e.message, "error"));
  };

  const changeStatus = async (app: Application, status: string) => {    try {
      await api.patch(`/api/applications/${app.id}`, { status });
      toast(t("Status changed to {status}", { status: t(status) }));
      load();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  const remove = async () => {
    if (!deleting) return;
    try {
      await api.delete(`/api/applications/${deleting.id}`);
      toast(t("Application deleted"));
      load();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  const statusSelect = (a: Application, compact = false) => (
    <select
      value={a.status}
      onChange={(e) => changeStatus(a, e.target.value)}
      aria-label={t("Status for {title}", { title: a.job.title })}
      className={
        compact
          ? "h-7 rounded-md border border-input bg-card px-1.5 text-[11px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          : "h-8 rounded-lg border border-input bg-card px-2 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      }
    >
      {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{t(s)}</option>)}
    </select>
  );

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow={t("Pipeline")}
        title={t("Applications Desk")}
        description={t("Press Prepare and the AI writes the CV, letter, email, questions and keywords for that one ad. You read them, you send them — nothing goes out on its own.")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Select value={statusFilter} aria-label={t("Filter applications by status")} onChange={(e) => setStatusFilter(e.target.value)} className="w-44">
              <option value="">{t("All statuses")}</option>
              {APP_STATUSES.map((s) => <option key={s} value={s}>{t(s)}</option>)}
            </Select>
            <Tabs
              tabs={[
                { value: "table", label: t("Table") },
                { value: "kanban", label: t("Kanban") },
              ]}
              value={view}
              onChange={(v) => setView(v as "table" | "kanban")}
            />
          </div>
        }
      />

      {error && items && (
        <p className="rounded-xl border border-red-500/25 bg-red-500/[0.05] p-3 text-sm text-red-700 dark:text-red-400">
          {t("{error} — showing the last results that loaded.", { error })}{" "}
          <button className="font-semibold underline" onClick={load}>{t("Try again")}</button>
        </p>
      )}

      {error && !items ? (
        <ErrorState message={error} onRetry={load} />
      ) : items === null ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20 rounded-2xl" />)}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={ListChecks}
          title={statusFilter ? t('No applications with status "{status}"', { status: t(statusFilter) }) : t("No applications tracked yet")}
          description={statusFilter
            ? t("Clear the status filter to see all of your tracked applications.")
            : t("Use the Track button on any job in Find Jobs to start tracking it here.")}
          action={statusFilter
            ? <Button variant="outline" onClick={() => setStatusFilter("")}>{t("Show all statuses")}</Button>
            : <Link to="/jobs" className={buttonClassName()}><Plus className="h-4 w-4" /> {t("Find jobs to track")}</Link>}
        />
      ) : view === "table" ? (
        <div className="overflow-hidden rounded-2xl border border-border/80 bg-card shadow-soft">
          <div className="scrollbar-thin overflow-x-auto">
            <table className="w-full min-w-[940px] text-sm">
              <thead>
                <tr className="border-b border-border/70 bg-muted/50 text-start text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  <th className="px-3 py-3 font-semibold">{t("Job")}</th>
                  <th className="px-3 py-3 font-semibold">{t("Status")}</th>
                  <th className="px-3 py-3 font-semibold">{t("How to apply")}</th>
                  <th className="px-3 py-3 font-semibold">{t("AI pack")}</th>
                  <th className="px-3 py-3 font-semibold">{t("Timeline")}</th>
                  <th className="px-3 py-3 font-semibold">{t("Notes")}</th>
                  <th className="px-3 py-3 text-end font-semibold">{t("Actions")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id} className="border-b border-border/60 transition-colors last:border-0 hover:bg-muted/30">
                    <td className="px-3 py-3.5">
                      <p className="max-w-[175px] truncate font-semibold" title={a.job.title}>{a.job.title}</p>
                      <p className="mt-0.5 max-w-[175px] truncate text-xs text-muted-foreground">{a.job.company} · {a.job.location}</p>
                    </td>
                    <td className="px-3 py-3.5">{statusSelect(a)}</td>
                    <td className="px-3 py-3.5">
                      <ApplyRouteTag job={a.job} />
                      {a.job.apply_emails[0] && (
                        <p className="mt-1 max-w-[120px] truncate text-[11px] text-muted-foreground"
                           title={a.job.apply_emails[0]}>{a.job.apply_emails[0]}</p>
                      )}
                    </td>
                    <td className="px-3 py-3.5">
                      <PackRow count={a.materials_count} busy={busyId === a.id}
                               onPrepare={() => prepare(a)} onView={() => openPack(a)} />
                    </td>
                    <td className="px-3 py-3.5">
                      <div className="space-y-0.5 whitespace-nowrap text-[11px]">
                        {a.date_applied && (
                          <p><span className="text-muted-foreground">{t("Applied")}</span> <span className="tabular-nums">{formatDate(a.date_applied)}</span></p>
                        )}
                        {a.follow_up_date && (
                          <p><span className="text-muted-foreground">{t("Follow-up")}</span> <span className="tabular-nums">{formatDate(a.follow_up_date)}</span></p>
                        )}
                        {a.interview_date && (
                          <p><span className="text-muted-foreground">{t("Interview")}</span> <span className="tabular-nums">{formatDate(a.interview_date)}</span></p>
                        )}
                        {!a.date_applied && !a.follow_up_date && !a.interview_date && (
                          <p className="text-muted-foreground">—</p>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-3.5">
                      <p className="line-clamp-2 max-w-[180px] text-xs text-muted-foreground" title={a.notes}>
                        {a.notes || "—"}
                      </p>
                    </td>
                    <td className="px-3 py-3.5">
                      <div className="flex justify-end gap-0.5">
                        {a.job.url && (
                          <Button size="icon" variant="ghost" className="h-8 w-8" title={t("Open job posting")} onClick={() => window.open(a.job.url, "_blank", "noopener")}>
                            <ExternalLink className="h-4 w-4" />
                          </Button>
                        )}
                        <Link
                          to={`/assistant?job=${a.job.id}`}
                          className={buttonClassName({ variant: "ghost", size: "icon", className: "h-8 w-8" })}
                          title={t("Write one document yourself in the Assistant")}
                          aria-label={t("Write one document yourself in the Assistant")}
                        >
                          <Bot className="h-4 w-4" />
                        </Link>
                        <Button size="icon" variant="ghost" className="h-8 w-8" title={t("Edit")} onClick={() => setEditing(a)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8" title={t("Delete")} onClick={() => setDeleting(a)}>
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((col) => {
            const colItems = items.filter((a) => a.status === col);
            return (
              <section key={col} className="rounded-2xl border border-border/70 bg-muted/25 p-2.5">
                <div className="mb-2 flex items-center justify-between px-1 py-1">
                  <StatusBadge status={col} />
                  <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-semibold tabular-nums text-muted-foreground">
                    {colItems.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {colItems.map((a) => (
                    <div key={a.id} className="rounded-xl border border-border/80 bg-card p-3 shadow-soft">
                      <p className="line-clamp-2 text-xs font-semibold leading-snug">{a.job.title}</p>
                      <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{a.job.company}</p>
                      <div className="mt-2 flex items-center gap-1.5">
                        <ApplyRouteTag job={a.job} />
                        <span className="truncate text-[10px] text-muted-foreground" title={a.job.apply_note}>
                          {a.job.apply_note}
                        </span>
                      </div>
                      <div className="mt-2.5">
                        <PackRow count={a.materials_count} busy={busyId === a.id}
                                 onPrepare={() => prepare(a)} onView={() => openPack(a)} />
                      </div>
                      <div className="mt-2.5 flex items-center justify-between">
                        {statusSelect(a, true)}
                        <div className="flex">
                          <Button size="icon" variant="ghost" className="h-7 w-7" title={t("Edit")} onClick={() => setEditing(a)}>
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button size="icon" variant="ghost" className="h-7 w-7" title={t("Delete")} onClick={() => setDeleting(a)}>
                            <Trash2 className="h-3.5 w-3.5 text-red-500" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                  {colItems.length === 0 && (
                    <p className="rounded-lg border border-dashed border-border/80 p-4 text-center text-[11px] text-muted-foreground">{t("Empty")}</p>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}

      <EditDialog app={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      <PackDialog pack={pack} onClose={() => setPack(null)} onChanged={load} onApplied={markFromPack} />
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        title={t("Delete application")}
        message={t('Remove the application for "{title}"? This cannot be undone.', { title: deleting?.job.title ?? "" })}
      />
    </div>
  );
}

function EditDialog({ app, onClose, onSaved }: { app: Application | null; onClose: () => void; onSaved: () => void }) {
  const { toast } = useToast();
  const { t } = useI18n();
  const [status, setStatus] = useState("");
  const [dateApplied, setDateApplied] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [interview, setInterview] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (app) {
      setStatus(app.status);
      setDateApplied(toInputDate(app.date_applied));
      setFollowUp(toInputDate(app.follow_up_date));
      setInterview(toInputDate(app.interview_date));
      setNotes(app.notes);
    }
  }, [app]);

  const save = async () => {
    if (!app) return;
    setSaving(true);
    try {
      const toIso = (d: string) => (d ? new Date(d + "T09:00:00").toISOString() : null);
      const patch: Record<string, string | null> = { status, notes };
      // An empty box that was already empty means "not set yet": leave the field out
      // so the backend can stamp the applied date. Only send null when clearing one.
      const dates: [string, string | null][] = [
        ["date_applied", app.date_applied],
        ["follow_up_date", app.follow_up_date],
        ["interview_date", app.interview_date],
      ];
      const inputs = [dateApplied, followUp, interview];
      dates.forEach(([field, existing], i) => {
        const value = toIso(inputs[i]);
        if (value !== null || existing) patch[field] = value;
      });
      await api.patch(`/api/applications/${app.id}`, patch);
      toast(t("Application updated"));
      onSaved();
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={!!app} onClose={onClose} title={app ? `${t("Edit")}: ${app.job.title}` : ""} description={app ? `${app.job.company} · ${app.job.location}` : ""}>
      <div className="space-y-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label>{t("Status")}</Label>
            <Select value={status} onChange={(e) => setStatus(e.target.value)} className="mt-1.5">
              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{t(s)}</option>)}
            </Select>
          </div>
          <div>
            <Label>{t("Date applied")}</Label>
            <Input type="date" value={dateApplied} onChange={(e) => setDateApplied(e.target.value)} className="mt-1.5" />
          </div>
          <div>
            <Label>{t("Follow-up date")}</Label>
            <Input type="date" value={followUp} onChange={(e) => setFollowUp(e.target.value)} className="mt-1.5" />
          </div>
          <div>
            <Label>{t("Interview date")}</Label>
            <Input type="date" value={interview} onChange={(e) => setInterview(e.target.value)} className="mt-1.5" />
          </div>
        </div>
        <div>
          <Label>{t("Notes")}</Label>
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} className="mt-1.5" rows={4}
                    placeholder={t("Contacts, salary expectations, interview feedback…")} />
        </div>
        <div className="flex justify-end gap-2 border-t border-border/70 pt-4">
          <Button variant="ghost" onClick={onClose}>{t("Cancel")}</Button>
          <Button onClick={save} disabled={saving}>{saving ? t("Saving…") : t("Save changes")}</Button>
        </div>
      </div>
    </Dialog>
  );
}
