import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Briefcase,
  FileText,
  FolderKanban,
  GraduationCap,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Target,
  Trash2,
  Upload,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "@/lib/api";
import type { EducationItem, Experience, Profile, Project, ResumeAutofill, Skill, TermSuggestion } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader } from "@/components/layout/page-header";
import { useToast } from "@/context/toast";
import { cn } from "@/lib/utils";

const REMOTE_OPTIONS = [
  { value: "open", label: "Open to all (remote / hybrid / onsite)" },
  { value: "remote", label: "Remote only" },
  { value: "hybrid", label: "Hybrid preferred" },
  { value: "onsite", label: "Onsite only" },
];

const WORK_TYPES = ["Full-time", "Part-time", "Internship", "Contract", "Freelance"];
const LEVELS = ["Intern", "Entry", "Junior", "Mid", "Senior"];
const LANGUAGES = ["Arabic", "English", "French", "German", "Other"];

const AUTOFILL_LABELS: Record<string, string> = {
  full_name: "Full name", email: "Email", phone: "Phone", city: "City", country: "Country",
  linkedin: "LinkedIn", github: "GitHub", portfolio: "Portfolio", summary: "Summary",
};
const AUTOFILL_ORDER = Object.keys(AUTOFILL_LABELS);

const sameText = (a?: string | null, b?: string | null) =>
  (a ?? "").trim().toLowerCase() === (b ?? "").trim().toLowerCase();

const SECTION_NAV: { id: string; label: string; icon: LucideIcon }[] = [
  { id: "basics", label: "Basic information", icon: UserRound },
  { id: "preferences", label: "Job preferences", icon: Target },
  { id: "skills", label: "Skills", icon: Sparkles },
  { id: "experience", label: "Work experience", icon: Briefcase },
  { id: "education", label: "Education", icon: GraduationCap },
  { id: "projects", label: "Projects", icon: FolderKanban },
  { id: "resume", label: "Resume file", icon: FileText },
];

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
          aria-label={label}
          placeholder={placeholder ?? "Type and press Enter"}
          onChange={(e) => setText(e.target.value)}
          // Committing on blur is what keeps a typed-but-unpressed tag from vanishing when
          // he goes straight to "Save profile".
          onBlur={add}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button type="button" variant="outline" size="icon" onClick={add} aria-label={`Add ${label}`}><Plus className="h-4 w-4" /></Button>
      </div>
      {values.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {values.map((v) => (
            <span key={v} className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/70 px-2 py-1 text-xs font-medium">
              {v}
              <button type="button" className="text-muted-foreground transition-colors hover:text-red-500" onClick={() => onChange(values.filter((x) => x !== v))} aria-label={`Remove ${v}`}>×</button>
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

function SuggestionList({ items, onUse }: {
  items: TermSuggestion[];
  onUse: (term: string, suggestion: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="mt-1.5 space-y-1">
      {items.map((s) => (
        <p key={`${s.kind}:${s.term}`} className="text-[11px] text-amber-700 dark:text-amber-400">
          Did you mean{" "}
          <button
            type="button"
            className="font-semibold underline decoration-amber-500/50 underline-offset-2 hover:decoration-amber-600"
            onClick={() => onUse(s.term, s.suggestion)}
          >
            {s.suggestion}
          </button>{" "}
          instead of “{s.term}”?
        </p>
      ))}
    </div>
  );
}

function ProfileSection({
  id,
  title,
  description,
  action,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card id={id} className="scroll-mt-24">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0 pb-4">
        <div className="min-w-0">
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription className="mt-1">{description}</CardDescription>}
        </div>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function FieldLabel({ children }: { children: ReactNode }) {
  // A span, not a label: the field's own <label> element wraps this text and its control.
  return <span className="text-xs font-medium text-muted-foreground">{children}</span>;
}

function ChipToggle({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground shadow-soft"
          : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}

export function ProfilePage() {
  const { toast } = useToast();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [confirmResumeDelete, setConfirmResumeDelete] = useState(false);
  // Negative ids for rows added in this session: they never collide with server
  // ids and keep React keys stable while the user edits or deletes sibling rows.
  const keySeq = useRef(-1);
  const newKey = () => keySeq.current--;

  const load = () => {
    setError(null);
    api.get<Profile>("/api/profile").then(setProfile).catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const [suggestions, setSuggestions] = useState<TermSuggestion[]>([]);
  // Re-check spelling whenever one of the term lists changes. 600 ms of quiet is
  // enough to catch a typo without a request per keystroke; suggestions are hints
  // only — nothing is rewritten until the user clicks one.
  const suggestionKey = profile
    ? [profile.skills.map((s) => s.name).join("|"), profile.desired_titles.join("|"),
       profile.preferred_locations.join("|")].join("||")
    : "";
  useEffect(() => {
    if (!profile) return;
    const payload = {
      titles: profile.desired_titles,
      skills: profile.skills.map((s) => s.name).filter((n) => n.trim()),
      locations: profile.preferred_locations,
    };
    const timer = setTimeout(() => {
      api.post<TermSuggestion[]>("/api/profile/term-suggestions", payload, { track: false })
        .then(setSuggestions)
        .catch(() => {});
    }, 600);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestionKey]);

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
    } finally {
      setConfirmResumeDelete(false);
    }
  };

  const [autofill, setAutofill] = useState<ResumeAutofill | null>(null);
  const [autofillLoading, setAutofillLoading] = useState(false);
  const [autofillApplying, setAutofillApplying] = useState(false);
  const [chosenFields, setChosenFields] = useState<Record<string, boolean>>({});
  const [chosenSkills, setChosenSkills] = useState<Record<string, boolean>>({});
  const [chosenExp, setChosenExp] = useState<boolean[]>([]);
  const [chosenEdu, setChosenEdu] = useState<boolean[]>([]);

  const expIsDuplicate = (exp: Experience) =>
    !!profile && profile.experiences.some((e) => sameText(e.title, exp.title)
      && sameText(e.company, exp.company) && sameText(e.start_date, exp.start_date));
  const eduIsDuplicate = (item: EducationItem) =>
    !!profile && profile.education.some((e) => sameText(e.degree, item.degree)
      && sameText(e.institution, item.institution));

  const runAutofill = async () => {
    if (!profile) return;
    setAutofillLoading(true);
    try {
      const data = await api.post<ResumeAutofill>("/api/profile/resume/autofill");
      const fieldDefaults: Record<string, boolean> = {};
      for (const key of Object.keys(data.fields)) {
        const current = profile[key as keyof Profile];
        fieldDefaults[key] = !(typeof current === "string" ? current : "").trim();
      }
      const skillDefaults: Record<string, boolean> = {};
      for (const name of data.skills) {
        skillDefaults[name] = !profile.skills.some((s) => sameText(s.name, name));
      }
      setChosenFields(fieldDefaults);
      setChosenSkills(skillDefaults);
      setChosenExp(data.experiences.map((e) => !expIsDuplicate(e)));
      setChosenEdu(data.education.map((e) => !eduIsDuplicate(e)));
      setAutofill(data);
      const total = Object.keys(data.fields).length + data.skills.length + data.experiences.length + data.education.length;
      if (!total) toast("Nothing readable was found in this CV.", "error");
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setAutofillLoading(false);
    }
  };

  const pickedCount = autofill
    ? Object.entries(autofill.fields).filter(([key]) => chosenFields[key]).length
      + autofill.skills.filter((name) => chosenSkills[name]).length
      + chosenExp.filter(Boolean).length
      + chosenEdu.filter(Boolean).length
    : 0;

  const applyAutofill = async () => {
    if (!autofill || !pickedCount) return;
    const fields = Object.fromEntries(Object.entries(autofill.fields).filter(([key]) => chosenFields[key]));
    const skills = autofill.skills.filter((name) => chosenSkills[name]);
    const experiences = autofill.experiences.filter((_, i) => chosenExp[i]);
    const education = autofill.education.filter((_, i) => chosenEdu[i]);
    setAutofillApplying(true);
    try {
      const updated = await api.post<Profile>("/api/profile/resume/autofill/apply", { fields, skills, experiences, education });
      setProfile(updated);
      setAutofill(null);
      toast(`Profile updated from your CV (${pickedCount} item${pickedCount === 1 ? "" : "s"})`);
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setAutofillApplying(false);
    }
  };

  if (!profile) {
    return (
      <div className="space-y-5">
        <PageHeader eyebrow="Your source of truth" title="Resume & Profile" />
        {error
          ? <ErrorState message={error} onRetry={load} />
          : (
            <>
              <Skeleton className="h-10 w-64" />
              <Skeleton className="h-96 rounded-2xl" />
              <Skeleton className="h-64 rounded-2xl" />
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

  const hintFor = (term: string, kind: TermSuggestion["kind"]) => {
    const wanted = term.trim().toLowerCase();
    if (!wanted) return undefined;
    return suggestions.find((s) => s.kind === kind && s.term.trim().toLowerCase() === wanted)?.suggestion;
  };
  const hintsFor = (kind: TermSuggestion["kind"], values: string[]) => {
    const current = new Set(values.map((v) => v.trim().toLowerCase()));
    return suggestions.filter((s) => s.kind === kind && current.has(s.term.trim().toLowerCase()));
  };
  const replaceTerm = (values: string[], term: string, suggestion: string) =>
    values.map((v) => (v.trim().toLowerCase() === term.trim().toLowerCase() ? suggestion : v));

  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  const saveButton = (size: "default" | "lg" = "default") => (
    <Button onClick={save} disabled={saving} size={size}>
      {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
      {saving ? "Saving…" : "Save profile"}
    </Button>
  );

  return (
    <div className="animate-fade-in space-y-5 pb-10">
      <PageHeader
        eyebrow="Your source of truth"
        title="Resume & Profile"
        description="This profile feeds match scores and everything the AI writes for you. Nothing is ever sent anywhere on its own."
        actions={saveButton()}
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="hidden xl:block">
          <nav className="sticky top-24 space-y-1 rounded-2xl border border-border/70 bg-card/70 p-2 shadow-soft backdrop-blur">
            <p className="px-3 py-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Sections</p>
            {SECTION_NAV.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => scrollTo(item.id)}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </button>
            ))}
          </nav>
        </aside>

        <div className="min-w-0 space-y-5">
          <ProfileSection
            id="basics"
            title="Basic information"
            description="Used in generated cover letters and emails — never invent anything beyond this."
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <label className="block"><FieldLabel>Full name</FieldLabel><Input className="mt-1.5" value={profile.full_name} onChange={(e) => set("full_name", e.target.value)} /></label>
              <label className="block"><FieldLabel>Email</FieldLabel><Input className="mt-1.5" type="email" value={profile.email} onChange={(e) => set("email", e.target.value)} /></label>
              <label className="block"><FieldLabel>Phone</FieldLabel><Input className="mt-1.5" value={profile.phone} onChange={(e) => set("phone", e.target.value)} /></label>
              <label className="block"><FieldLabel>Country</FieldLabel><Input className="mt-1.5" value={profile.country} onChange={(e) => set("country", e.target.value)} /></label>
              <label className="block"><FieldLabel>City</FieldLabel><Input className="mt-1.5" value={profile.city} onChange={(e) => set("city", e.target.value)} /></label>
              <label className="block"><FieldLabel>LinkedIn</FieldLabel><Input className="mt-1.5" value={profile.linkedin} onChange={(e) => set("linkedin", e.target.value)} /></label>
              <label className="block"><FieldLabel>GitHub</FieldLabel><Input className="mt-1.5" value={profile.github} onChange={(e) => set("github", e.target.value)} /></label>
              <label className="block"><FieldLabel>Portfolio</FieldLabel><Input className="mt-1.5" value={profile.portfolio} onChange={(e) => set("portfolio", e.target.value)} /></label>
              <div className="sm:col-span-2 lg:col-span-1">
                <FieldLabel>Languages</FieldLabel>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {LANGUAGES.map((l) => (
                    <ChipToggle
                      key={l}
                      active={profile.languages.includes(l)}
                      onClick={() => set("languages", profile.languages.includes(l) ? profile.languages.filter((x) => x !== l) : [...profile.languages, l])}
                    >
                      {l}
                    </ChipToggle>
                  ))}
                </div>
              </div>
              <label className="sm:col-span-2 lg:col-span-3 block">
                <FieldLabel>Professional summary</FieldLabel>
                <Textarea className="mt-1.5" rows={3} value={profile.summary}
                          onChange={(e) => set("summary", e.target.value)}
                          placeholder="2-3 sentences about who you are and what you do." />
              </label>
            </div>
          </ProfileSection>

          <ProfileSection
            id="preferences"
            title="Job preferences"
            description="These drive your match scores and scheduled searches."
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <TagsInput label="Desired job titles" values={profile.desired_titles} onChange={(v) => set("desired_titles", v)} placeholder="e.g. Flutter Developer" />
                <SuggestionList
                  items={hintsFor("title", profile.desired_titles)}
                  onUse={(term, suggestion) => set("desired_titles", replaceTerm(profile.desired_titles, term, suggestion))}
                />
              </div>
              <div>
                <TagsInput label="Preferred locations" values={profile.preferred_locations} onChange={(v) => set("preferred_locations", v)} placeholder="e.g. Cairo, Remote" />
                <SuggestionList
                  items={hintsFor("location", profile.preferred_locations)}
                  onUse={(term, suggestion) => set("preferred_locations", replaceTerm(profile.preferred_locations, term, suggestion))}
                />
              </div>
              <label className="block">
                <FieldLabel>Remote preference</FieldLabel>
                <Select className="mt-1.5" value={profile.remote_preference} onChange={(e) => set("remote_preference", e.target.value)}>
                  {REMOTE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </Select>
              </label>
              <div>
                <FieldLabel>Target levels</FieldLabel>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {LEVELS.map((l) => (
                    <ChipToggle
                      key={l}
                      active={profile.target_levels.includes(l)}
                      onClick={() => set("target_levels", profile.target_levels.includes(l) ? profile.target_levels.filter((x) => x !== l) : [...profile.target_levels, l])}
                    >
                      {l}
                    </ChipToggle>
                  ))}
                </div>
              </div>
              <div>
                <FieldLabel>Work types</FieldLabel>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {WORK_TYPES.map((t) => (
                    <ChipToggle
                      key={t}
                      active={profile.work_types.includes(t)}
                      onClick={() => set("work_types", profile.work_types.includes(t) ? profile.work_types.filter((x) => x !== t) : [...profile.work_types, t])}
                    >
                      {t}
                    </ChipToggle>
                  ))}
                </div>
                <p className="mt-1.5 text-[11px] text-muted-foreground">Not part of the match score — filter by employment type in Find Jobs to narrow results.</p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  <FieldLabel>Min. salary</FieldLabel>
                  <Input className="mt-1.5" type="number" min={0} value={profile.min_salary ?? ""}
                         onChange={(e) => set("min_salary", e.target.value === "" ? null : Number(e.target.value))} />
                </label>
                <label className="block">
                  <FieldLabel>Currency</FieldLabel>
                  <Select className="mt-1.5" value={profile.salary_currency} onChange={(e) => set("salary_currency", e.target.value)}>
                    <option value="EGP">EGP</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="SAR">SAR</option>
                    <option value="AED">AED</option>
                  </Select>
                </label>
              </div>
            </div>
          </ProfileSection>

          <ProfileSection
            id="skills"
            title="Skills"
            description="Rate each skill 1 (beginner) to 5 (expert). These are matched against every posting."
            action={
              <Button variant="outline" size="sm" onClick={() => set("skills", [...profile.skills, { name: "", level: 3, years: null, _key: newKey() }])}>
                <Plus className="h-4 w-4" /> Add skill
              </Button>
            }
          >
            <div className="space-y-2.5">
              {profile.skills.length > 0 && (
                <div className="hidden gap-2 px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground sm:grid sm:grid-cols-[minmax(0,1fr)_140px_120px_40px]">
                  <span>Skill</span><span>Level</span><span>Years</span><span />
                </div>
              )}
              {profile.skills.map((s, i) => {
                const hint = hintFor(s.name, "skill");
                return (
                  <div key={s.id ?? s._key ?? i} className="rounded-xl border border-border/70 bg-card p-3 transition-colors hover:border-border">
                    <div className="grid grid-cols-1 items-center gap-2 sm:grid-cols-[minmax(0,1fr)_140px_120px_40px]">
                      <Input value={s.name} aria-label={`Skill ${i + 1} name`} placeholder="Skill name" onChange={(e) => patchSkill(i, { name: e.target.value })} />
                      <Select value={String(s.level)} aria-label={`Skill ${i + 1} level`} onChange={(e) => patchSkill(i, { level: Number(e.target.value) })}>
                        {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>Level {n}</option>)}
                      </Select>
                      <Input type="number" min={0} step={0.5} aria-label={`Skill ${i + 1} years of experience`} placeholder="Years" value={s.years ?? ""} onChange={(e) => patchSkill(i, { years: e.target.value === "" ? null : Number(e.target.value) })} />
                      <Button variant="ghost" size="icon" className="h-9 w-9 justify-self-end text-muted-foreground hover:text-red-600" onClick={() => set("skills", profile.skills.filter((_, idx) => idx !== i))} aria-label={`Remove ${s.name || "skill"}`}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    {hint && (
                      <SuggestionList
                        items={[{ term: s.name, suggestion: hint, kind: "skill" }]}
                        onUse={() => patchSkill(i, { name: hint })}
                      />
                    )}
                  </div>
                );
              })}
              {profile.skills.length === 0 && (
                <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                  No skills yet. Add the ones you can honestly do — they drive the match score.
                </p>
              )}
            </div>
          </ProfileSection>

          <ProfileSection
            id="experience"
            title="Work experience"
            action={
              <Button variant="outline" size="sm" onClick={() => set("experiences", [...profile.experiences, { title: "", company: "", location: "", start_date: null, end_date: null, current: false, description: "", _key: newKey() }])}>
                <Plus className="h-4 w-4" /> Add experience
              </Button>
            }
          >
            <div className="space-y-4">
              {profile.experiences.map((e, i) => (
                <div key={e.id ?? e._key ?? i} className="rounded-xl border border-border/70 bg-card p-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold">{e.title || "New role"}{e.company ? ` · ${e.company}` : ""}</p>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-600" onClick={() => set("experiences", profile.experiences.filter((_, idx) => idx !== i))} aria-label="Remove experience">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-3">
                    <label className="block"><FieldLabel>Job title</FieldLabel><Input className="mt-1" value={e.title} onChange={(ev) => patchExp(i, { title: ev.target.value })} /></label>
                    <label className="block"><FieldLabel>Company</FieldLabel><Input className="mt-1" value={e.company} onChange={(ev) => patchExp(i, { company: ev.target.value })} /></label>
                    <label className="block"><FieldLabel>Location</FieldLabel><Input className="mt-1" value={e.location} onChange={(ev) => patchExp(i, { location: ev.target.value })} /></label>
                    <label className="block"><FieldLabel>Start (YYYY-MM)</FieldLabel><Input className="mt-1" value={e.start_date ?? ""} placeholder="2024-06" onChange={(ev) => patchExp(i, { start_date: ev.target.value || null })} /></label>
                    <label className="block"><FieldLabel>End (YYYY-MM)</FieldLabel><Input className="mt-1" value={e.end_date ?? ""} placeholder="2025-01" disabled={e.current} onChange={(ev) => patchExp(i, { end_date: ev.target.value || null })} /></label>
                    <div className="flex items-end pb-1">
                      <label className="flex items-center gap-2 text-sm text-muted-foreground">
                        <input type="checkbox" checked={e.current} onChange={(ev) => patchExp(i, { current: ev.target.checked })} className="h-4 w-4" />
                        Current role
                      </label>
                    </div>
                  </div>
                  <label className="mt-3 block">
                    <FieldLabel>Description</FieldLabel>
                    <Textarea className="mt-1" rows={2} value={e.description} onChange={(ev) => patchExp(i, { description: ev.target.value })} />
                  </label>
                </div>
              ))}
              {profile.experiences.length === 0 && (
                <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                  No experience added yet. Add the roles you actually held.
                </p>
              )}
            </div>
          </ProfileSection>

          <ProfileSection
            id="education"
            title="Education"
            action={
              <Button variant="outline" size="sm" onClick={() => set("education", [...profile.education, { degree: "", institution: "", field: "", start_date: null, end_date: null, description: "", _key: newKey() }])}>
                <Plus className="h-4 w-4" /> Add education
              </Button>
            }
          >
            <div className="space-y-4">
              {profile.education.map((e, i) => (
                <div key={e.id ?? e._key ?? i} className="rounded-xl border border-border/70 bg-card p-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold">{e.degree || "New degree"}{e.institution ? ` · ${e.institution}` : ""}</p>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-600" onClick={() => set("education", profile.education.filter((_, idx) => idx !== i))} aria-label="Remove education">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <label className="mt-3 grid gap-3 sm:grid-cols-3 block">
                    <label className="block"><FieldLabel>Degree</FieldLabel><Input className="mt-1" value={e.degree} onChange={(ev) => patchEdu(i, { degree: ev.target.value })} /></label>
                    <label className="block"><FieldLabel>Institution</FieldLabel><Input className="mt-1" value={e.institution} onChange={(ev) => patchEdu(i, { institution: ev.target.value })} /></label>
                    <label className="block"><FieldLabel>Field</FieldLabel><Input className="mt-1" value={e.field} onChange={(ev) => patchEdu(i, { field: ev.target.value })} /></label>
                    <label className="block"><FieldLabel>Start</FieldLabel><Input className="mt-1" value={e.start_date ?? ""} onChange={(ev) => patchEdu(i, { start_date: ev.target.value || null })} /></label>
                    <label className="block"><FieldLabel>End</FieldLabel><Input className="mt-1" value={e.end_date ?? ""} onChange={(ev) => patchEdu(i, { end_date: ev.target.value || null })} /></label>
                  </label>
                  <label className="mt-3 block">
                    <FieldLabel>Description</FieldLabel>
                    <Textarea className="mt-1" rows={2} value={e.description} onChange={(ev) => patchEdu(i, { description: ev.target.value })} />
                  </label>
                </div>
              ))}
              {profile.education.length === 0 && (
                <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                  No education added yet.
                </p>
              )}
            </div>
          </ProfileSection>

          <ProfileSection
            id="projects"
            title="Projects & portfolio"
            action={
              <Button variant="outline" size="sm" onClick={() => set("projects", [...profile.projects, { name: "", description: "", url: "", technologies: [], _key: newKey() }])}>
                <Plus className="h-4 w-4" /> Add project
              </Button>
            }
          >
            <div className="space-y-4">
              {profile.projects.map((p, i) => (
                <div key={p.id ?? p._key ?? i} className="rounded-xl border border-border/70 bg-card p-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold">{p.name || "New project"}</p>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-600" onClick={() => set("projects", profile.projects.filter((_, idx) => idx !== i))} aria-label="Remove project">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <label className="mt-3 grid gap-3 sm:grid-cols-2 block">
                    <label className="block"><FieldLabel>Project name</FieldLabel><Input className="mt-1" value={p.name} onChange={(ev) => patchProj(i, { name: ev.target.value })} /></label>
                    <label className="block"><FieldLabel>URL</FieldLabel><Input className="mt-1" value={p.url} onChange={(ev) => patchProj(i, { url: ev.target.value })} /></label>
                  </label>
                  <div className="mt-3"><FieldLabel>Description</FieldLabel><Textarea className="mt-1" rows={2} value={p.description} onChange={(ev) => patchProj(i, { description: ev.target.value })} /></div>
                  <label className="mt-3 block">
                    <FieldLabel>Technologies (comma separated)</FieldLabel>
                    <CommaInput className="mt-1" values={p.technologies}
                                placeholder="Flutter, Firebase, REST APIs"
                                onCommit={(v) => patchProj(i, { technologies: v })} />
                  </label>
                </div>
              ))}
              {profile.projects.length === 0 && (
                <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                  No projects added yet. Real projects you built are worth showing.
                </p>
              )}
            </div>
          </ProfileSection>

          <ProfileSection
            id="resume"
            title="Resume file"
            description="PDF, TXT, DOCX or MD up to 5 MB. Text is extracted from all of them so the AI can use it. Old .doc files: save as .docx or PDF first. Files are never executed."
          >
            {profile.resume_filename ? (
              <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/70 bg-muted/30 p-4">
                <div className="rounded-lg bg-card p-2 text-foreground shadow-soft">
                  <FileText className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold">{profile.resume_filename}</p>
                  <p className="text-xs text-muted-foreground">
                    {profile.resume_text ? "Text extracted — the AI can read it" : "No readable text — match scores can't use it"}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={runAutofill}
                  disabled={autofillLoading || !profile.resume_text}
                  title={profile.resume_text ? "Fill your profile from this resume" : "No readable text in this file"}
                >
                  {autofillLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  Auto-fill from CV
                </Button>
                <Button variant="outline" size="sm" onClick={() => setConfirmResumeDelete(true)}>Remove</Button>
              </div>
            ) : (
              <label className={`flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/20 px-6 py-12 text-center transition-colors hover:border-foreground/25 hover:bg-muted/40 ${uploading ? "pointer-events-none opacity-60" : "cursor-pointer"}`}>
                <Upload className="h-5 w-5 text-muted-foreground/60" aria-hidden />
                <p className="mt-4 text-[15px] font-semibold">{uploading ? "Uploading…" : "Upload your resume"}</p>
                <p className="mt-1 text-xs text-muted-foreground">PDF / TXT / DOCX / MD, max 5 MB</p>
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,.txt,.docx,.md"
                  disabled={uploading}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadResume(f);
                    e.target.value = "";
                  }}
                />
              </label>
            )}
          </ProfileSection>

          <Dialog
            open={!!autofill}
            onClose={() => setAutofill(null)}
            title="Auto-fill from your CV"
            description="Read literally from your uploaded resume. Nothing is saved until you press Apply."
            wide
          >
            {autofill && (
              <div className="space-y-5">
                {Object.keys(autofill.fields).length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold">Contact &amp; summary</h3>
                    <div className="mt-2 divide-y divide-border/60 overflow-hidden rounded-xl border border-border/70">
                      {AUTOFILL_ORDER.filter((key) => key in autofill.fields).map((key) => {
                        const value = autofill.fields[key];
                        const profileValue = profile[key as keyof Profile];
                        const current = typeof profileValue === "string" ? profileValue : "";
                        const replaces = !!current.trim();
                        return (
                          <label key={key} className="flex cursor-pointer items-start gap-3 p-3 transition-colors hover:bg-muted/30">
                            <input
                              type="checkbox"
                              className="mt-0.5 h-4 w-4 shrink-0 accent-primary"
                              checked={!!chosenFields[key]}
                              onChange={(e) => setChosenFields((s) => ({ ...s, [key]: e.target.checked }))}
                            />
                            <span className="min-w-0 flex-1">
                              <span className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                                {AUTOFILL_LABELS[key]}
                                {replaces && (
                                  <span className="rounded-md bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-400">
                                    replaces current
                                  </span>
                                )}
                              </span>
                              <span className={cn(
                                "mt-0.5 block break-words text-xs leading-relaxed",
                                chosenFields[key] ? "text-foreground" : "text-muted-foreground",
                                key === "summary" && "line-clamp-3"
                              )}>
                                {value}
                              </span>
                              {replaces && (
                                <span className="mt-0.5 line-clamp-2 block break-words text-[11px] text-muted-foreground/70">
                                  Now: {current}
                                </span>
                              )}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </section>
                )}

                {autofill.skills.length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold">
                      Skills <span className="font-normal text-muted-foreground">({autofill.skills.length})</span>
                    </h3>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {autofill.skills.map((name) => {
                        const exists = profile.skills.some((s) => sameText(s.name, name));
                        const on = !!chosenSkills[name];
                        return (
                          <button
                            key={name}
                            type="button"
                            aria-pressed={on}
                            disabled={exists}
                            title={exists ? "Already on your profile" : undefined}
                            onClick={() => setChosenSkills((s) => ({ ...s, [name]: !on }))}
                            className={cn(
                              "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
                              exists
                                ? "cursor-default border-border bg-muted/50 text-muted-foreground line-through"
                                : on
                                  ? "border-primary bg-primary text-primary-foreground"
                                  : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
                            )}
                          >
                            {name}
                          </button>
                        );
                      })}
                    </div>
                  </section>
                )}

                {autofill.experiences.length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold">Work experience</h3>
                    <div className="mt-2 space-y-2">
                      {autofill.experiences.map((exp, i) => {
                        const exists = expIsDuplicate(exp);
                        return (
                          <label key={i} className={cn(
                            "flex items-start gap-3 rounded-xl border p-3",
                            exists ? "border-border/60 bg-muted/30" : "border-border/80 bg-card"
                          )}>
                            <input
                              type="checkbox"
                              className="mt-0.5 h-4 w-4 shrink-0 accent-primary"
                              disabled={exists}
                              checked={!!chosenExp[i]}
                              onChange={(e) => setChosenExp((s) => s.map((v, idx) => (idx === i ? e.target.checked : v)))}
                            />
                            <span className="min-w-0 flex-1">
                              <span className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                                {exp.title}{exp.company ? ` · ${exp.company}` : ""}
                                {exists && <span className="text-[10px] font-medium text-muted-foreground">already on your profile</span>}
                              </span>
                              <span className="mt-0.5 block text-[11px] tabular-nums text-muted-foreground">
                                {exp.start_date ?? "—"} → {exp.current ? "Present" : exp.end_date ?? "—"}
                              </span>
                              {exp.description && (
                                <span className="mt-0.5 line-clamp-3 block whitespace-pre-line text-[11px] leading-relaxed text-muted-foreground">
                                  {exp.description}
                                </span>
                              )}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </section>
                )}

                {autofill.education.length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold">Education</h3>
                    <div className="mt-2 space-y-2">
                      {autofill.education.map((edu, i) => {
                        const exists = eduIsDuplicate(edu);
                        return (
                          <label key={i} className={cn(
                            "flex items-start gap-3 rounded-xl border p-3",
                            exists ? "border-border/60 bg-muted/30" : "border-border/80 bg-card"
                          )}>
                            <input
                              type="checkbox"
                              className="mt-0.5 h-4 w-4 shrink-0 accent-primary"
                              disabled={exists}
                              checked={!!chosenEdu[i]}
                              onChange={(e) => setChosenEdu((s) => s.map((v, idx) => (idx === i ? e.target.checked : v)))}
                            />
                            <span className="min-w-0 flex-1">
                              <span className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                                {edu.degree}{edu.institution ? ` · ${edu.institution}` : ""}
                                {exists && <span className="text-[10px] font-medium text-muted-foreground">already on your profile</span>}
                              </span>
                              {edu.field && <span className="mt-0.5 block text-[11px] text-muted-foreground">{edu.field}</span>}
                              <span className="mt-0.5 block text-[11px] tabular-nums text-muted-foreground">
                                {edu.start_date ?? "—"} → {edu.end_date ?? "—"}
                              </span>
                              {edu.description && (
                                <span className="mt-0.5 block text-[11px] leading-relaxed text-muted-foreground">{edu.description}</span>
                              )}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </section>
                )}

                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-4">
                  <p className="text-xs text-muted-foreground">
                    {pickedCount} of {Object.keys(autofill.fields).length + autofill.skills.length
                      + autofill.experiences.length + autofill.education.length} found items selected
                  </p>
                  <div className="flex gap-2">
                    <Button variant="outline" onClick={() => setAutofill(null)}>Cancel</Button>
                    <Button onClick={applyAutofill} disabled={!pickedCount || autofillApplying}>
                      {autofillApplying && <Loader2 className="h-4 w-4 animate-spin" />}
                      Apply selected
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </Dialog>

          <ConfirmDialog
            open={confirmResumeDelete}
            onClose={() => setConfirmResumeDelete(false)}
            onConfirm={() => void deleteResume()}
            title="Remove your resume file"
            message="The uploaded file and the text read from it are deleted. Your saved profile details stay — only the resume goes. You would have to upload the file again."
            confirmLabel="Remove resume"
          />

          <div className="flex justify-end border-t border-border/60 pt-5">
            {saveButton("lg")}
          </div>
        </div>
      </div>
    </div>
  );
}
