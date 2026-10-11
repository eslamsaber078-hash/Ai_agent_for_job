import { useEffect, useRef, useState } from "react";
import { Bot, Columns3, ListChecks, Pencil, Plus, Table2, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api, qs } from "@/lib/api";
import { APP_STATUSES, type Application } from "@/lib/types";
import { formatDate, toInputDate } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { useToast } from "@/context/toast";

const COLUMNS = ["Discovered", "Interested", "Preparing", "Applied", "Interview", "Offer", "Rejected", "Archived"];

export function ApplicationsPage() {
  const { toast } = useToast();
  const [items, setItems] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"table" | "kanban">("table");
  const [statusFilter, setStatusFilter] = useState("");
  const [editing, setEditing] = useState<Application | null>(null);
  const [deleting, setDeleting] = useState<Application | null>(null);
  const reqId = useRef(0);

  const load = () => {
    const my = ++reqId.current;
    setError(null);
    api
      .get<Application[]>(`/api/applications${qs({ status: statusFilter })}`)
      .then((d) => { if (my === reqId.current) setItems(d); })
      .catch((e) => { if (my === reqId.current) setError(e.message); });
  };

  useEffect(load, [statusFilter]);

  const changeStatus = async (app: Application, status: string) => {
    try {
      await api.patch(`/api/applications/${app.id}`, { status });
      toast(`Status changed to ${status}`);
      load();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  const remove = async () => {
    if (!deleting) return;
    try {
      await api.delete(`/api/applications/${deleting.id}`);
      toast("Application deleted");
      load();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Applications Tracker</h1>
          <p className="text-sm text-muted-foreground">Track every application from discovery to offer</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-44">
            <option value="">All statuses</option>
            {APP_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
          <Tabs
            tabs={[
              { value: "table", label: "Table" },
              { value: "kanban", label: "Kanban" },
            ]}
            value={view}
            onChange={(v) => setView(v as "table" | "kanban")}
          />
        </div>
      </div>

      {error && items && (
        <p className="rounded-lg border border-red-500/40 bg-red-500/5 p-3 text-sm text-red-600 dark:text-red-400">
          {error} — showing the last results that loaded.{" "}
          <button className="underline" onClick={load}>Try again</button>
        </p>
      )}

      {error && !items ? (
        <ErrorState message={error} onRetry={load} />
      ) : items === null ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={ListChecks}
          title={statusFilter ? `No applications with status "${statusFilter}"` : "No applications tracked yet"}
          description={statusFilter
            ? "Clear the status filter to see all of your tracked applications."
            : "Use the Track button on any job in Find Jobs to start tracking it here."}
          action={statusFilter
            ? <Button variant="outline" onClick={() => setStatusFilter("")}>Show all statuses</Button>
            : <Link to="/jobs"><Button><Plus className="h-4 w-4" /> Find jobs to track</Button></Link>}
        />
      ) : view === "table" ? (
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="p-3 font-medium">Job</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium">Applied</th>
                <th className="p-3 font-medium">Follow-up</th>
                <th className="p-3 font-medium">Interview</th>
                <th className="p-3 font-medium">Notes</th>
                <th className="p-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="p-3">
                    <p className="font-medium">{a.job.title}</p>
                    <p className="text-xs text-muted-foreground">{a.job.company} · {a.job.location}</p>
                  </td>
                  <td className="p-3">
                    <select
                      value={a.status}
                      onChange={(e) => changeStatus(a, e.target.value)}
                      className="h-8 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="p-3 text-xs">{formatDate(a.date_applied)}</td>
                  <td className="p-3 text-xs">{formatDate(a.follow_up_date)}</td>
                  <td className="p-3 text-xs">{formatDate(a.interview_date)}</td>
                  <td className="max-w-[200px] truncate p-3 text-xs text-muted-foreground" title={a.notes}>
                    {a.notes || "—"}
                  </td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1">
                      {a.job.url && (
                        <Button size="icon" variant="ghost" title="Open job posting" onClick={() => window.open(a.job.url, "_blank", "noopener")}>
                          <Table2 className="h-4 w-4" />
                        </Button>
                      )}
                      <Link to={`/assistant?job=${a.job.id}`}>
                        <Button size="icon" variant="ghost" title="Open in AI Assistant"><Bot className="h-4 w-4" /></Button>
                      </Link>
                      <Button size="icon" variant="ghost" title="Edit" onClick={() => setEditing(a)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button size="icon" variant="ghost" title="Delete" onClick={() => setDeleting(a)}>
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((col) => {
            const colItems = items.filter((a) => a.status === col);
            return (
              <div key={col} className="rounded-xl border bg-muted/30 p-2">
                <div className="mb-2 flex items-center justify-between px-1">
                  <StatusBadge status={col} />
                  <span className="text-xs text-muted-foreground">{colItems.length}</span>
                </div>
                <div className="space-y-2">
                  {colItems.map((a) => (
                    <div key={a.id} className="rounded-lg border bg-card p-3 shadow-sm">
                      <p className="text-xs font-semibold leading-snug">{a.job.title}</p>
                      <p className="mt-0.5 text-[11px] text-muted-foreground">{a.job.company}</p>
                      <div className="mt-2 flex items-center justify-between">
                        <select
                          value={a.status}
                          onChange={(e) => changeStatus(a, e.target.value)}
                          className="h-7 rounded-md border border-input bg-background px-1.5 text-[11px]"
                        >
                          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                        <div className="flex">
                          <Button size="icon" variant="ghost" className="h-7 w-7" title="Edit" onClick={() => setEditing(a)}>
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button size="icon" variant="ghost" className="h-7 w-7" title="Delete" onClick={() => setDeleting(a)}>
                            <Trash2 className="h-3.5 w-3.5 text-red-500" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                  {colItems.length === 0 && (
                    <p className="rounded-lg border border-dashed p-4 text-center text-[11px] text-muted-foreground">Empty</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <EditDialog app={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        title="Delete application"
        message={`Remove the application for "${deleting?.job.title}"? This cannot be undone.`}
      />
    </div>
  );
}

function EditDialog({ app, onClose, onSaved }: { app: Application | null; onClose: () => void; onSaved: () => void }) {
  const { toast } = useToast();
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
      await api.patch(`/api/applications/${app.id}`, {
        status,
        date_applied: toIso(dateApplied),
        follow_up_date: toIso(followUp),
        interview_date: toIso(interview),
        notes,
      });
      toast("Application updated");
      onSaved();
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={!!app} onClose={onClose} title={app ? `Edit: ${app.job.title}` : ""} description={app ? `${app.job.company} · ${app.job.location}` : ""}>
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label>Status</Label>
            <Select value={status} onChange={(e) => setStatus(e.target.value)} className="mt-1.5">
              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
          </div>
          <div>
            <Label>Date applied</Label>
            <Input type="date" value={dateApplied} onChange={(e) => setDateApplied(e.target.value)} className="mt-1.5" />
          </div>
          <div>
            <Label>Follow-up date</Label>
            <Input type="date" value={followUp} onChange={(e) => setFollowUp(e.target.value)} className="mt-1.5" />
          </div>
          <div>
            <Label>Interview date</Label>
            <Input type="date" value={interview} onChange={(e) => setInterview(e.target.value)} className="mt-1.5" />
          </div>
        </div>
        <div>
          <Label>Notes</Label>
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} className="mt-1.5" rows={4}
                    placeholder="Contacts, salary expectations, interview feedback…" />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={saving}>{saving ? "Saving…" : "Save changes"}</Button>
        </div>
      </div>
    </Dialog>
  );
}
