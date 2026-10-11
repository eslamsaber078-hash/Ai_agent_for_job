import { useEffect, useState } from "react";
import { FileText, Loader2, Plus, Save, Trash2, Upload, UserRound } from "lucide-react";
import { api } from "@/lib/api";
import type { EducationItem, Experience, Profile, Project, Skill } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/context/toast";

const REMOTE_OPTIONS = [
  { value: "open", label: "Open to all (remote / hybrid / onsite)" },
  { value: "remote", label: "Remote only" },
  { value: "hybrid", label: "Hybrid preferred" },
  { value: "onsite", label: "Onsite only" },
];

const WORK_TYPES = ["Full-time", "Part-time", "Internship", "Contract", "Freelance"];
const LEVELS = ["Intern", "Entry", "Junior", "Mid", "Senior"];
const LANGUAGES = ["Arabic", "English", "French", "German", "Other"];

function TagsInput({ label, values, onChange, placeholder }: { label: string; values: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [text, setText] = useState("");
  const add = () => {
    const v = text.trim();
    if (v && !values.includes(v)) onChange([...values, v]);
    setText("");
  };
  return (
    <div>
      <Label>{label}</Label>
      <div className="mt-1.5 flex gap-2">
        <Input
          value={text}
          placeholder={placeholder ?? "Type and press Enter"}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button type="button" variant="outline" size="icon" onClick={add}><Plus className="h-4 w-4" /></Button>
      </div>
      {values.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {values.map((v) => (
            <span key={v} className="inline-flex items-center gap-1 rounded-full border bg-muted px-2.5 py-0.5 text-xs">
              {v}
              <button type="button" className="text-muted-foreground hover:text-red-500" onClick={() => onChange(values.filter((x) => x !== v))}>×</button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function CommaInput({ values, onCommit, className, ...rest }: {
  values: string[];
  onCommit: (v: string[]) => void;
  className?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <Input
      {...rest}
      className={className}
      value={draft ?? values.join(", ")}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        if (draft === null) return;
        onCommit(draft.split(",").map((x) => x.trim()).filter(Boolean));
        setDraft(null);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
      }}
    />
  );
}

export function ProfilePage() {
  const { toast } = useToast();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const load = () => {
    setError(null);
    api.get<Profile>("/api/profile").then(setProfile).catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const set = <K extends keyof Profile>(key: K, value: Profile[K]) =>
    setProfile((p) => (p ? { ...p, [key]: value } : p));

  const save = async () => {
    if (!profile) return;
    const blankSkill = profile.skills.findIndex((s) => !s.name.trim());
    if (blankSkill >= 0) {
      toast(`Skill #${blankSkill + 1} has no name — fill it in or remove it.`, "error");
      return;
    }
    const steps: [string, () => Promise<unknown>][] = [
      ["basic details", () => api.put("/api/profile", {
        full_name: profile.full_name, email: profile.email, phone: profile.phone,
        country: profile.country, city: profile.city, linkedin: profile.linkedin,
        github: profile.github, portfolio: profile.portfolio, summary: profile.summary,
        desired_titles: profile.desired_titles, preferred_locations: profile.preferred_locations,
        remote_preference: profile.remote_preference, work_types: profile.work_types,
        min_salary: profile.min_salary, salary_currency: profile.salary_currency,
        languages: profile.languages, target_levels: profile.target_levels,
      })],
      ["skills", () => api.put("/api/profile/skills", profile.skills)],
      ["work experience", () => api.put("/api/profile/experiences", profile.experiences)],
      ["education", () => api.put("/api/profile/education", profile.education)],
      ["projects", () => api.put("/api/profile/projects", profile.projects)],
    ];
    setSaving(true);
    for (let i = 0; i < steps.length; i++) {
      const [label, run] = steps[i];
      try {
        await run();
      } catch (e: any) {
        const rest = steps.length - i - 1;
        toast(`Saved up to "${label}", but that part failed: ${e.message}${rest > 0 ? ` (${rest} section(s) not saved)` : ""}`, "error");
        setSaving(false);
        return;
      }
    }
    toast("Profile saved");
    setSaving(false);
  };

  const uploadResume = async (file: File) => {
    setUploading(true);
    try {
      const updated = await api.upload<Profile>("/api/profile/resume", file);
      setProfile((p) => (p ? { ...p, resume_filename: updated.resume_filename, resume_text: updated.resume_text } : p));
      toast(`Resume "${file.name}" uploaded${updated.resume_text ? " and text extracted" : ""}`);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setUploading(false);
    }
  };

  const deleteResume = async () => {
    try {
      await api.delete("/api/profile/resume");
      setProfile((p) => (p ? { ...p, resume_filename: null, resume_text: null } : p));
      toast("Resume removed");
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  if (!profile) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold">Resume &amp; Profile</h1>
        {error
          ? <ErrorState message={error} onRetry={load} />
          : (
            <>
              <Skeleton className="h-10 w-64" />
              <Skeleton className="h-96" />
            </>
          )}
      </div>
    );
  }

  const patchSkill = (i: number, patch: Partial<Skill>) =>
    set("skills", profile.skills.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  const patchExp = (i: number, patch: Partial<Experience>) =>
    set("experiences", profile.experiences.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  const patchEdu = (i: number, patch: Partial<EducationItem>) =>
    set("education", profile.education.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  const patchProj = (i: number, patch: Partial<Project>) =>
    set("projects", profile.projects.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));

  return (
    <div className="space-y-6 pb-16">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Resume & Profile</h1>
          <p className="text-sm text-muted-foreground">
            This profile is the source of truth for match scores and all AI-generated content.
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={save} disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {saving ? "Saving…" : "Save profile"}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base"><UserRound className="h-4 w-4" /> Basic information</CardTitle>
          <CardDescription>Used in generated cover letters and emails — never invent anything beyond this.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div><Label>Full name</Label><Input className="mt-1.5" value={profile.full_name} onChange={(e) => set("full_name", e.target.value)} /></div>
          <div><Label>Email</Label><Input className="mt-1.5" type="email" value={profile.email} onChange={(e) => set("email", e.target.value)} /></div>
          <div><Label>Phone</Label><Input className="mt-1.5" value={profile.phone} onChange={(e) => set("phone", e.target.value)} /></div>
          <div><Label>Country</Label><Input className="mt-1.5" value={profile.country} onChange={(e) => set("country", e.target.value)} /></div>
          <div><Label>City</Label><Input className="mt-1.5" value={profile.city} onChange={(e) => set("city", e.target.value)} /></div>
          <div><Label>LinkedIn</Label><Input className="mt-1.5" value={profile.linkedin} onChange={(e) => set("linkedin", e.target.value)} /></div>
          <div><Label>GitHub</Label><Input className="mt-1.5" value={profile.github} onChange={(e) => set("github", e.target.value)} /></div>
          <div><Label>Portfolio</Label><Input className="mt-1.5" value={profile.portfolio} onChange={(e) => set("portfolio", e.target.value)} /></div>
          <div className="sm:col-span-2 lg:col-span-1">
            <Label>Languages</Label>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {LANGUAGES.map((l) => {
                const on = profile.languages.includes(l);
                return (
                  <button
                    key={l}
                    type="button"
                    onClick={() => set("languages", on ? profile.languages.filter((x) => x !== l) : [...profile.languages, l])}
                    className={`rounded-full border px-2.5 py-0.5 text-xs ${on ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent"}`}
                  >
                    {l}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="sm:col-span-2 lg:col-span-3">
            <Label>Professional summary</Label>
            <Textarea className="mt-1.5" rows={3} value={profile.summary}
                      onChange={(e) => set("summary", e.target.value)}
                      placeholder="2-3 sentences about who you are and what you do." />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Job preferences</CardTitle>
          <CardDescription>These drive your match scores and scheduled searches.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <TagsInput label="Desired job titles" values={profile.desired_titles} onChange={(v) => set("desired_titles", v)} placeholder="e.g. Flutter Developer" />
          <TagsInput label="Preferred locations" values={profile.preferred_locations} onChange={(v) => set("preferred_locations", v)} placeholder="e.g. Cairo, Remote" />
          <div>
            <Label>Remote preference</Label>
            <Select className="mt-1.5" value={profile.remote_preference} onChange={(e) => set("remote_preference", e.target.value)}>
              {REMOTE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </Select>
          </div>
          <div>
            <Label>Target levels</Label>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {LEVELS.map((l) => {
                const on = profile.target_levels.includes(l);
                return (
                  <button key={l} type="button" onClick={() => set("target_levels", on ? profile.target_levels.filter((x) => x !== l) : [...profile.target_levels, l])}
                          className={`rounded-full border px-2.5 py-0.5 text-xs ${on ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent"}`}>
                    {l}
                  </button>
                );
              })}
            </div>
          </div>
          <div>
            <Label>Work types</Label>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {WORK_TYPES.map((t) => {
                const on = profile.work_types.includes(t);
                return (
                  <button key={t} type="button" onClick={() => set("work_types", on ? profile.work_types.filter((x) => x !== t) : [...profile.work_types, t])}
                          className={`rounded-full border px-2.5 py-0.5 text-xs ${on ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent"}`}>
                    {t}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label>Min. salary</Label>
              <Input className="mt-1.5" type="number" min={0} value={profile.min_salary ?? ""}
                     onChange={(e) => set("min_salary", e.target.value === "" ? null : Number(e.target.value))} />
            </div>
            <div>
              <Label>Currency</Label>
              <Select className="mt-1.5" value={profile.salary_currency} onChange={(e) => set("salary_currency", e.target.value)}>
                <option value="EGP">EGP</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="SAR">SAR</option>
                <option value="AED">AED</option>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Skills</CardTitle>
          <CardDescription>Rate each skill 1 (beginner) to 5 (expert).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {profile.skills.map((s, i) => (
            <div key={i} className="flex flex-wrap items-end gap-2">
              <div className="w-44"><Input value={s.name} placeholder="Skill name" onChange={(e) => patchSkill(i, { name: e.target.value })} /></div>
              <div className="w-28">
                <Select value={String(s.level)} onChange={(e) => patchSkill(i, { level: Number(e.target.value) })}>
                  {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>Level {n}</option>)}
                </Select>
              </div>
              <div className="w-24"><Input type="number" min={0} step={0.5} placeholder="Years" value={s.years ?? ""} onChange={(e) => patchSkill(i, { years: e.target.value === "" ? null : Number(e.target.value) })} /></div>
              <Button variant="ghost" size="icon" onClick={() => set("skills", profile.skills.filter((_, idx) => idx !== i))}>
                <Trash2 className="h-4 w-4 text-red-500" />
              </Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => set("skills", [...profile.skills, { name: "", level: 3, years: null }])}>
            <Plus className="h-4 w-4" /> Add skill
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Work experience</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {profile.experiences.map((e, i) => (
            <div key={i} className="rounded-lg border p-3 space-y-3">
              <div className="grid gap-2 sm:grid-cols-3">
                <div><Label>Job title</Label><Input className="mt-1" value={e.title} onChange={(ev) => patchExp(i, { title: ev.target.value })} /></div>
                <div><Label>Company</Label><Input className="mt-1" value={e.company} onChange={(ev) => patchExp(i, { company: ev.target.value })} /></div>
                <div><Label>Location</Label><Input className="mt-1" value={e.location} onChange={(ev) => patchExp(i, { location: ev.target.value })} /></div>
                <div><Label>Start (YYYY-MM)</Label><Input className="mt-1" value={e.start_date ?? ""} placeholder="2024-06" onChange={(ev) => patchExp(i, { start_date: ev.target.value || null })} /></div>
                <div><Label>End (YYYY-MM)</Label><Input className="mt-1" value={e.end_date ?? ""} placeholder="2025-01" disabled={e.current} onChange={(ev) => patchExp(i, { end_date: ev.target.value || null })} /></div>
                <div className="flex items-end gap-2 pb-1">
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={e.current} onChange={(ev) => patchExp(i, { current: ev.target.checked })} className="h-4 w-4" />
                    Current role
                  </label>
                  <Button variant="ghost" size="icon" className="ml-auto" onClick={() => set("experiences", profile.experiences.filter((_, idx) => idx !== i))}>
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              </div>
              <div>
                <Label>Description</Label>
                <Textarea className="mt-1" rows={2} value={e.description} onChange={(ev) => patchExp(i, { description: ev.target.value })} />
              </div>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => set("experiences", [...profile.experiences, { title: "", company: "", location: "", start_date: null, end_date: null, current: false, description: "" }])}>
            <Plus className="h-4 w-4" /> Add experience
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Education</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {profile.education.map((e, i) => (
            <div key={i} className="rounded-lg border p-3 space-y-3">
              <div className="grid gap-2 sm:grid-cols-3">
                <div><Label>Degree</Label><Input className="mt-1" value={e.degree} onChange={(ev) => patchEdu(i, { degree: ev.target.value })} /></div>
                <div><Label>Institution</Label><Input className="mt-1" value={e.institution} onChange={(ev) => patchEdu(i, { institution: ev.target.value })} /></div>
                <div><Label>Field</Label><Input className="mt-1" value={e.field} onChange={(ev) => patchEdu(i, { field: ev.target.value })} /></div>
                <div><Label>Start</Label><Input className="mt-1" value={e.start_date ?? ""} onChange={(ev) => patchEdu(i, { start_date: ev.target.value || null })} /></div>
                <div><Label>End</Label><Input className="mt-1" value={e.end_date ?? ""} onChange={(ev) => patchEdu(i, { end_date: ev.target.value || null })} /></div>
                <div className="flex items-end pb-1">
                  <Button variant="ghost" size="icon" className="ml-auto" onClick={() => set("education", profile.education.filter((_, idx) => idx !== i))}>
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              </div>
              <div>
                <Label>Description</Label>
                <Textarea className="mt-1" rows={2} value={e.description} onChange={(ev) => patchEdu(i, { description: ev.target.value })} />
              </div>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => set("education", [...profile.education, { degree: "", institution: "", field: "", start_date: null, end_date: null, description: "" }])}>
            <Plus className="h-4 w-4" /> Add education
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Projects & portfolio</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {profile.projects.map((p, i) => (
            <div key={i} className="rounded-lg border p-3 space-y-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <div><Label>Project name</Label><Input className="mt-1" value={p.name} onChange={(ev) => patchProj(i, { name: ev.target.value })} /></div>
                <div><Label>URL</Label><Input className="mt-1" value={p.url} onChange={(ev) => patchProj(i, { url: ev.target.value })} /></div>
              </div>
              <div><Label>Description</Label><Textarea className="mt-1" rows={2} value={p.description} onChange={(ev) => patchProj(i, { description: ev.target.value })} /></div>
              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <Label>Technologies (comma separated)</Label>
                  <CommaInput className="mt-1" values={p.technologies}
                              placeholder="Flutter, Firebase, REST APIs"
                              onCommit={(v) => patchProj(i, { technologies: v })} />
                </div>
                <Button variant="ghost" size="icon" onClick={() => set("projects", profile.projects.filter((_, idx) => idx !== i))}>
                  <Trash2 className="h-4 w-4 text-red-500" />
                </Button>
              </div>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => set("projects", [...profile.projects, { name: "", description: "", url: "", technologies: [] }])}>
            <Plus className="h-4 w-4" /> Add project
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base"><FileText className="h-4 w-4" /> Resume file</CardTitle>
          <CardDescription>PDF, TXT, DOC, DOCX or MD up to 5 MB. Text is extracted from PDF, TXT, MD and DOCX so the AI can use it. Files are never executed.</CardDescription>
        </CardHeader>
        <CardContent>
          {profile.resume_filename ? (
            <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3">
              <FileText className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">{profile.resume_filename}</span>
              <span className="text-xs text-muted-foreground">
                {profile.resume_text ? "text extracted — the AI can read it" : "no readable text — match scores can't use it"}
              </span>
              <div className="ml-auto flex gap-2">
                <Button variant="outline" size="sm" onClick={deleteResume}>Remove</Button>
              </div>
            </div>
          ) : (
            <label className={`flex flex-col items-center justify-center rounded-xl border border-dashed py-10 text-center hover:bg-muted/40 ${uploading ? "pointer-events-none opacity-60" : "cursor-pointer"}`}>
              <Upload className="h-6 w-6 text-muted-foreground" />
              <p className="mt-2 text-sm font-medium">{uploading ? "Uploading…" : "Click to upload your resume"}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">PDF / TXT / DOC / DOCX / MD, max 5 MB</p>
              <input
                type="file"
                className="hidden"
                accept=".pdf,.txt,.doc,.docx,.md"
                disabled={uploading}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) uploadResume(f);
                  e.target.value = "";
                }}
              />
            </label>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={save} disabled={saving} size="lg">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {saving ? "Saving…" : "Save profile"}
        </Button>
      </div>
    </div>
  );
}
