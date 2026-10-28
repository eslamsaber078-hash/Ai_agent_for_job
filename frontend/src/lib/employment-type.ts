import type { Lang } from "@/context/i18n";

/**
 * Provider employment_type values arrive as a soup ("Permanent employment (unbefristeter
 * arbeitsvertrag), professional / experienced", "Vast dienstverband (onbepaalde tijd)").
 * This decomposes any such value into canonical translatable parts; values where nothing
 * is recognised (provider junk) are shown as-is rather than dropped.
 */

/** [substring, canonical dictionary key | null to strip without output], ordered. */
const TOKENS: [string, string | null][] = [
  ["international", null],
  ["b2b", null],
  ["eor", null],
  ["unbefristeter arbeitsvertrag", "Permanent"],
  ["befristeter arbeitsvertrag", "Temporary"],
  ["vast dienstverband", "Permanent"],
  ["onbepaalde tijd", "Permanent"],
  ["indefinite contract", "Permanent"],
  ["contrato indefinido", "Permanent"],
  ["open-ended contract", "Permanent"],
  ["contrat à durée indéterminée", "Permanent"],
  ["cdi", "Permanent"],
  ["alternance", "Apprenticeship"],
  ["ausbildung", "Apprenticeship"],
  ["apprenticeship", "Apprenticeship"],
  ["full or part time", "Full or part time"],
  ["full-time", "Full Time"],
  ["part-time", "Part Time"],
  ["full time", "Full Time"],
  ["part time", "Part Time"],
  ["fulltime", "Full Time"],
  ["parttime", "Part Time"],
  ["permanent", "Permanent"],
  ["fixed-term", "Temporary"],
  ["fixed term", "Temporary"],
  ["temporary", "Temporary"],
  ["internship", "Internship"],
  ["praktikum", "Internship"],
  ["intern", "Internship"],
  ["working student", "Working student"],
  ["werkstudent", "Working student"],
  ["student college", "Student"],
  ["student", "Student"],
  ["volunteer", "Volunteer"],
  ["freelancer", "Freelance"],
  ["freiberufler", "Freelance"],
  ["selbstständiger", "Freelance"],
  ["independent contractor", "Contractor"],
  ["freelance", "Freelance"],
  ["contractor", "Contractor"],
  ["contract", "Contract"],
  ["employee", "Employee"],
  ["minijob", "Side job"],
  ["geringfügige beschäftigung", "Side job"],
  ["nebentätigkeit", "Side job"],
  ["beschäftigung", "Side job"],
  ["side", "Side job"],
  ["berufseinstieg", "Entry"],
  ["berufserfahren", "Experienced"],
  ["hilfstätigkeit", "Student assistant"],
  ["teamleitung", "Team lead"],
  ["geschäftsleitung", "Management"],
  ["arbeitskraft", "Worker"],
  ["management", "Management"],
  ["supervisor", "Supervisor"],
  ["débutant", "Entry"],
  ["instapniveau", "Entry"],
  ["no experience required", "Entry"],
  ["professional", "Experienced"],
  ["experienced", "Experienced"],
  ["entry", "Entry"],
  ["mid", "Mid"],
  ["senior", "Senior"],
  ["executive", "Executive"],
  ["director", "Director"],
  ["manager", "Manager"],
  ["associate", "Associate"],
  ["trainee", "Trainee"],
  ["customer success", "Customer Success"],
  ["development", "Development"],
  ["administration", "Administration"],
  ["writing", "Writing"],
  ["design", "Design"],
  ["marketing", "Marketing"],
  ["education", "Education"],
  ["sales", "Sales"],
  ["other", "Other"],
  ["full", "Full Time"],
  ["part", "Part Time"],
  ["fr", null],
];

export function employmentTypeLabel(raw: string, t: (key: string) => string, lang: Lang): string {
  if (!raw) return "";
  const tokens = raw.split(/\s*(?:,\s*|\/\s*|&\s*|_\s*|\s+-\s+|\s*:\s*)\s*/);
  const keys: string[] = [];
  for (let tok of tokens) {
    let rest = tok.toLowerCase().replace(/\([^)]*\)/g, " ").replace(/\[[^\]]*\]/g, " ");
    for (const [pat, key] of TOKENS) {
      if (!rest.includes(pat)) continue;
      if (key) keys.push(key);
      rest = rest.split(pat).join(" ");
    }
  }
  const seen = new Set<string>();
  const uniq = keys.filter((k) => (seen.has(k) ? false : (seen.add(k), true)));
  if (!uniq.length) return raw;
  return uniq.map((k) => t(k)).join(lang === "ar" ? "، " : ", ");
}
