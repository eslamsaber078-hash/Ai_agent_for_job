import { useEffect, useRef, useState } from "react";
import { Bot, Copy, Download, FileDown, FileText, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { api, qs } from "@/lib/api";
import { MATERIAL_LABELS, type PreparedApplication, type PreparedMaterial, type Job } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { fileName, saveBlob } from "@/lib/download";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Tabs } from "@/components/ui/tabs";
import { ApplyRoute } from "./apply-route";
import { MarkedText, suggestedItems } from "./marked-text";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";

export interface Pack {
  job: Job;
  applicationId: number;
  materials: PreparedMaterial[];
}

/** The documents one click prepared for this ad, with the route the ad named. */
export function PackDialog({ pack, onClose, onChanged }: {
  pack: Pack | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const { toast } = useToast();
  const { t } = useI18n();
  const [materials, setMaterials] = useState<PreparedMaterial[]>([]);
  const [kind, setKind] = useState("cv");
  const [busy, setBusy] = useState(false);
  const [savingPdf, setSavingPdf] = useState<"marked" | "clean" | null>(null);
  const packRef = useRef<Pack | null>(pack);

  useEffect(() => {
    packRef.current = pack;
    if (!pack) return;
    setMaterials(pack.materials);
    const order = ["cv", "cover_letter", "email", "questions", "keywords"];
    const first = order.find((k) => pack.materials.some((m) => m.kind === k)) ?? pack.materials[0]?.kind ?? "cv";
    setKind(first);
  }, [pack]);

  if (!pack) return null;
  const current = materials.find((m) => m.kind === kind);
  const isCv = kind === "cv";
  const added = suggestedItems(current?.content ?? "");

  const rebuild = async () => {
    const jobId = pack.job.id;
    setBusy(true);
    try {
      const res = await api.post<PreparedApplication>("/api/applications/prepare", { job_id: jobId });
      // He can close this pack and open another one while the write is still running;
      // that response must not land on the new job's dialog.
      if (packRef.current?.job.id !== jobId) return;
      setMaterials(res.materials);
      toast(t("The pack was rebuilt from what your profile holds today"));
      onChanged();
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      if (packRef.current?.job.id === jobId) setBusy(false);
    }
  };

  const copy = () => {
    if (!current) return;
    navigator.clipboard.writeText(current.content)
      .then(() => toast(t("Copied to clipboard")))
      .catch(() => toast(t("Could not copy — select the text and copy manually"), "error"));
  };

  const download = () => {
    if (!current) return;
    saveBlob(
      new Blob([current.content], { type: "text/markdown;charset=utf-8" }),
      `${current.kind}_${(pack.job.company || "job").replace(/[^\w-]+/g, "")}.md`
    );
  };

  const savePdf = async (marked: boolean) => {
    const { applicationId, job } = pack;
    setSavingPdf(marked ? "marked" : "clean");
    try {
      const blob = await api.downloadPdf(
        `/api/applications/${applicationId}/materials/cv/pdf${qs({ marked })}`
      );
      saveBlob(blob, fileName(marked ? "CV_review" : "CV", job.title, job.company));
      toast(
        marked
          ? t("Review copy saved — the lines the assistant added are printed in red")
          : t("Send copy saved — the added lines are printed in black, without the red marks")
      );
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      if (packRef.current?.applicationId === applicationId) setSavingPdf(null);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={`${t("Application pack")} — ${pack.job.title}`}
      description={`${pack.job.company} · ${pack.job.location}`}
    >
      <div className="space-y-5">
        <ApplyRoute job={pack.job} emailBody={materials.find((m) => m.kind === "email")?.content} />

        {materials.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/80 px-6 py-10 text-center">
            <div className="mx-auto w-fit rounded-xl border border-border/70 bg-muted/40 p-3 text-muted-foreground">
              <FileText className="h-6 w-6" />
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{t("Nothing has been prepared for this ad yet.")}</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Button onClick={rebuild} disabled={busy}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
                {t("Prepare CV, letter, email and questions")}
              </Button>
              <Button
                variant="outline"
                onClick={() => savePdf(false)}
                disabled={savingPdf !== null}
                title={t("Download a CV PDF written for this ad, built only from your profile")}
              >
                {savingPdf === "clean" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FileDown className="h-4 w-4" />
                )}{" "}
                {t("Download CV PDF")}
              </Button>
            </div>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto pb-1">
              <Tabs
                value={kind}
                onChange={setKind}
                className="h-auto min-h-10"
                tabs={materials.map((m) => ({ value: m.kind, label: t(MATERIAL_LABELS[m.kind] ?? m.kind) }))}
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                {current?.template_based ? (
                  <Badge variant="warning">{t("Template draft")}</Badge>
                ) : (
                  <Badge variant="success">
                    <Sparkles className="h-3 w-3" /> {t("AI draft")}
                  </Badge>
                )}
                <span>{t("Written {date}", { date: formatDateTime(current?.created_at ?? null) })}</span>
                {isCv && added.length > 0 && (
                  <Badge variant="outline" className="border-red-500/40 bg-red-500/5 text-red-700 dark:text-red-400">
                    {t("{count} added for this ad — confirm them", { count: added.length })}
                  </Badge>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Button size="sm" variant="outline" onClick={copy}>
                  <Copy className="h-3.5 w-3.5" /> {t("Copy")}
                </Button>
                {isCv && (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => savePdf(true)}
                      disabled={savingPdf !== null}
                      title={t("Download the copy you check before sending — additions the assistant suggested are printed in red")}
                    >
                      {savingPdf === "marked" ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <FileDown className="h-3.5 w-3.5" />
                      )}{" "}
                      {t("CV PDF with red marks")}
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => savePdf(false)}
                      disabled={savingPdf !== null}
                      title={t("Download the copy for the employer — the red marks are gone and the added lines stay as normal text")}
                    >
                      {savingPdf === "clean" ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <FileDown className="h-3.5 w-3.5" />
                      )}{" "}
                      {t("Clean CV PDF")}
                    </Button>
                  </>
                )}
                <Button size="sm" variant="outline" onClick={download}>
                  <Download className="h-3.5 w-3.5" /> {t("Save .md")}
                </Button>
                <Button size="sm" variant="ghost" onClick={rebuild} disabled={busy}>
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}{" "}
                  {t("Rebuild")}
                </Button>
              </div>
            </div>

            <div className="scrollbar-thin max-h-[440px] overflow-y-auto rounded-xl border border-border/80 bg-muted/30 p-4">
              {current?.content ? (
                <MarkedText text={current.content} />
              ) : (
                <p className="text-xs text-muted-foreground">
                  {t("This document came back empty — rebuild the pack.")}
                </p>
              )}
            </div>

            {isCv && added.length > 0 && (
              <p className="text-[11px] leading-relaxed text-red-700 dark:text-red-400">
                {added.join(" · ")} {t("— these are the lines the assistant added above. Check every one you cannot back up before the clean copy goes out — it prints them in black.")}
              </p>
            )}

            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {t("Every line without a red mark comes straight from what you entered in")}{" "}
              <Link to="/profile" className="font-medium text-primary underline underline-offset-2">
                {t("Resume & Profile")}
              </Link>
              {t(". Red lines are the assistant's additions for this ad; the clean PDF prints them in black without the marks. The CV is rebuilt for ATS parsers — standard headings, plain single-column text — and the readiness score is at the bottom of this review. Read it, confirm what you can back up, then apply yourself — nothing here is sent for you.")}
            </p>
          </>
        )}
      </div>
    </Dialog>
  );
}

export function PackRow({ count, busy, onPrepare, onView }: {
  count: number;
  busy?: boolean;
  onPrepare: () => void;
  onView: () => void;
}) {
  const { t } = useI18n();
  if (count > 0) {
    return (
      <Button size="sm" variant="outline" onClick={onView} title={t("{count} documents prepared for this ad", { count })}>
        <FileText className="h-3.5 w-3.5" /> {t("{count} docs", { count })}
      </Button>
    );
  }
  return (
    <Button size="sm" onClick={onPrepare} disabled={busy} title={t("Write the CV, letter, email, questions and keywords for this ad")}>
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Bot className="h-3.5 w-3.5" />} {t("Prepare")}
    </Button>
  );
}
