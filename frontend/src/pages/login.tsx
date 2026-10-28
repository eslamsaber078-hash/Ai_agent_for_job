import { useRef, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  BriefcaseBusiness,
  Eye,
  EyeOff,
  Languages,
  Loader2,
  Lock,
  Phone,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useAuth } from "@/context/auth";
import { useToast } from "@/context/toast";
import { useI18n } from "@/context/i18n";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const PHONE_RE = /^(?:\+[1-9]\d{7,14}|01\d{9})$/;
const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";

/** A phone field holds a number: letters and symbols are dropped as they are typed. */
function sanitizePhone(raw: string): string {
  const plus = raw.trimStart().startsWith("+");
  const latin = [...raw]
    .map((ch) => {
      const digit = ARABIC_DIGITS.indexOf(ch);
      return digit >= 0 ? String(digit) : ch;
    })
    .join("");
  const digits = latin.replace(/\D/g, "").slice(0, 15);
  return (plus ? "+" : "") + digits;
}

function authError(t: (key: string) => string, err: unknown, registering: boolean): string {
  if (err instanceof ApiError) {
    if (err.status === 0 || err.status >= 500) return t("We can't reach the server right now. Try again in a bit.");
    if (err.status === 401) return t("The phone number or password is wrong. Check them and try again.");
    if (err.status === 409 && registering) return t("This phone number already has an account. Try logging in.");
    if (err.status === 400 || err.status === 422) {
      return t("Check your details and phone number. The password must be 6–128 characters.");
    }
    if (err.status === 429) return t("Too many attempts in a short time. Wait a bit and try again.");
  }
  return t("We couldn't complete the request. Try again.");
}

export function LoginPage() {
  const { user, login, register, busy } = useAuth();
  const { toast } = useToast();
  const { lang, setLang, t } = useI18n();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const submitting = useRef(false);
  const registering = mode === "register";
  const disabled = busy || pending;

  function switchMode(next: "login" | "register") {
    if (disabled || submitting.current) return;
    setMode(next);
    setPassword("");
    setConfirmation("");
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled || submitting.current) return;
    setError(null);
    if (registering && !fullName.trim()) {
      setError(t("Write your full name."));
      return;
    }
    if (!phone) {
      setError(t("Write your phone number."));
      return;
    }
    if (!PHONE_RE.test(phone)) {
      setError(t("The phone number is digits only — write it like 01xxxxxxxxx or +20xxxxxxxxxx."));
      return;
    }
    if (password.length < 6 || password.length > 128) {
      setError(t("The password must be 6–128 characters."));
      return;
    }
    if (registering && password !== confirmation) {
      setError(t("The password confirmation doesn't match. Write the same password again."));
      return;
    }
    submitting.current = true;
    setPending(true);
    try {
      const credentials = { phone: phone.trim(), password };
      if (registering) {
        await register({ ...credentials, full_name: fullName.trim() });
        navigate("/profile", { replace: true });
        toast(t("Your account is ready! Complete your skills and upload your CV, then start with Import."));
      } else {
        await login(credentials);
        navigate("/", { replace: true });
      }
      setPassword("");
      setConfirmation("");
    } catch (err) {
      setError(authError(t, err, registering));
      setPassword("");
      setConfirmation("");
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  if (user) return <Navigate to="/" replace />;

  return (
    <main className="relative min-h-screen bg-background">
      <button
        type="button"
        onClick={() => setLang(lang === "ar" ? "en" : "ar")}
        className="absolute end-4 top-4 z-10 flex h-9 items-center gap-1.5 rounded-lg border border-border/70 bg-card/80 px-2.5 text-xs font-semibold text-muted-foreground backdrop-blur transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={t("Switch language")}
        title={t("Switch language")}
      >
        <Languages className="h-4 w-4" />
        {lang === "ar" ? "English" : "عربي"}
      </button>

      <div className="grid grid-cols-1 min-h-screen lg:grid-cols-[1.02fr_1fr]">
        <section className="relative hidden flex-col justify-between overflow-hidden bg-primary p-10 text-primary-foreground lg:flex xl:p-14">
          <div className="surface-grid absolute inset-0 opacity-40" aria-hidden />
          <div className="relative flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-foreground text-primary shadow-lift">
              <BriefcaseBusiness className="h-5 w-5" />
            </div>
            <div>
              <p className="text-lg font-bold leading-tight tracking-tight" dir="ltr">JobHunter</p>
              <p className="text-xs text-primary-foreground/70">{t("Your AI job-search desk")}</p>
            </div>
          </div>

          <div className="relative max-w-lg space-y-8">
            <div className="space-y-4">
              <p className="text-xs font-medium text-primary-foreground/60">{t("Your personal job-search desk")}</p>
              <h1 className="text-4xl font-bold leading-[1.25] xl:text-[44px]">
                {t("Your next job")}
                <br />
                {t("starts here.")}
              </h1>
              <p className="max-w-md text-sm leading-relaxed text-primary-foreground/75">
                {t("Every real job in one place, and your profile is the basis for everything we write for you — no invented words, no made-up data.")}
              </p>
            </div>

            <ul className="space-y-4">
              {[
                { icon: Sparkles, title: t("Real, organised search"), text: t("Jobs from real public sources — no fake listings.") },
                { icon: ShieldCheck, title: t("Your data is yours"), text: t("Every account has its own profile and jobs — nobody sees anyone else's.") },
                { icon: Send, title: t("No auto-sending"), text: t("We write the CV and message; you review and send.") },
              ].map((item) => (
                <li key={item.title} className="flex items-start gap-3">
                  <item.icon className="mt-0.5 h-4 w-4 shrink-0 text-primary-foreground/50" />
                  <div>
                    <p className="text-sm font-semibold">{item.title}</p>
                    <p className="text-xs leading-relaxed text-primary-foreground/65">{item.text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <p className="relative text-[11px] text-primary-foreground/50">
            {t("Your own account — your data is isolated and nobody else can see it.")}
          </p>
        </section>

        <section className="flex items-center justify-center px-4 py-10 sm:px-8 lg:px-12">
          <div className="w-full max-w-[420px]">
            <div className="mb-8 flex items-center gap-2.5 lg:hidden">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
                <BriefcaseBusiness className="h-5 w-5" />
              </div>
              <div>
                <p className="text-base font-bold leading-tight" dir="ltr">JobHunter</p>
                <p className="text-[11px] text-muted-foreground">{t("Your AI job-search desk")}</p>
              </div>
            </div>

            <div className="rounded-xl border border-border/80 bg-card p-6 shadow-lift sm:p-8">
              <div className="space-y-1.5">
                <h2 className="text-2xl font-bold tracking-tight">
                  {registering ? t("Create a new account") : t("Welcome back")}
                </h2>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {registering
                    ? t("With your phone number and a simple password, so you can start right away.")
                    : t("Log in to your account and continue where you left off.")}
                </p>
              </div>

              <div className="mt-6 grid grid-cols-2 gap-1.5 rounded-xl border border-border/70 bg-muted/60 p-1" aria-label={t("Choose login or sign-up")}>
                {[
                  { value: "login" as const, label: t("Log in") },
                  { value: "register" as const, label: t("Sign up") },
                ].map((tab) => {
                  const active = mode === tab.value;
                  return (
                    <button
                      key={tab.value}
                      type="button"
                      disabled={disabled}
                      aria-pressed={active}
                      onClick={() => switchMode(tab.value)}
                      className={cn(
                        "h-9 rounded-lg text-sm font-medium transition-colors",
                        active ? "bg-card text-foreground shadow-soft" : "text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {tab.label}
                    </button>
                  );
                })}
              </div>

              <form
                onSubmit={submit}
                aria-busy={disabled}
                className="mt-6"
                onInvalidCapture={() => setError(t("Check the required details. The password must be 6–128 characters."))}
              >
                <fieldset disabled={disabled} className="space-y-4">
                  {registering && (
                    <div className="space-y-1.5">
                      <Label htmlFor="auth-name">{t("Full name")}</Label>
                      <div className="relative">
                        <UserRound className="pointer-events-none absolute end-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          id="auth-name"
                          name="full_name"
                          autoComplete="name"
                          required
                          className="h-11 pe-10"
                          value={fullName}
                          onChange={(event) => { setFullName(event.target.value); setError(null); }}
                        />
                      </div>
                    </div>
                  )}

                  <div className="space-y-1.5">
                    <Label htmlFor="auth-phone">{t("Phone number")}</Label>
                    <div className="relative">
                      <Phone className="pointer-events-none absolute end-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        id="auth-phone"
                        name="phone"
                        type="tel"
                        inputMode="tel"
                        autoComplete="tel"
                        dir="ltr"
                        required
                        maxLength={16}
                        className="h-11 pe-10 text-start"
                        placeholder="01xxxxxxxxx"
                        value={phone}
                        onChange={(event) => { setPhone(sanitizePhone(event.target.value)); setError(null); }}
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="auth-password">{t("Password")}</Label>
                    <div className="relative">
                      <Lock className="pointer-events-none absolute end-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        key={mode}
                        id="auth-password"
                        name="password"
                        type={showPassword ? "text" : "password"}
                        title=""
                        autoComplete={registering ? "new-password" : "current-password"}
                        dir="ltr"
                        required
                        minLength={6}
                        maxLength={128}
                        aria-describedby="auth-password-help"
                        className="h-11 ps-11 pe-10"
                        value={password}
                        onChange={(event) => { setPassword(event.target.value); setError(null); }}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((v) => !v)}
                        className="absolute start-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                        aria-label={showPassword ? t("Hide password") : t("Show password")}
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    <p id="auth-password-help" className="text-[11px] text-muted-foreground">{t("6–128 characters.")}</p>
                  </div>

                  {registering && (
                    <div className="space-y-1.5">
                      <Label htmlFor="auth-confirmation">{t("Confirm password")}</Label>
                      <div className="relative">
                        <ShieldCheck className="pointer-events-none absolute end-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          id="auth-confirmation"
                          name="confirm_password"
                          type={showPassword ? "text" : "password"}
                          title=""
                          autoComplete="new-password"
                          dir="ltr"
                          required
                          minLength={6}
                          maxLength={128}
                          className="h-11 pe-10"
                          value={confirmation}
                          onChange={(event) => { setConfirmation(event.target.value); setError(null); }}
                        />
                      </div>
                    </div>
                  )}

                  {error && (
                    <p id="auth-error" role="alert" className="rounded-lg border border-destructive/25 bg-destructive/[0.06] p-3 text-sm leading-relaxed text-destructive">
                      {error}
                    </p>
                  )}

                  <Button type="submit" className="h-11 w-full text-[15px]" disabled={disabled}>
                    {disabled ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <ArrowLeft className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />}
                    {disabled ? t("One moment…") : registering ? t("Create your account and start") : t("Log in to your account")}
                  </Button>
                </fieldset>
              </form>
            </div>

            <p className="mt-6 text-center text-[11px] leading-relaxed text-muted-foreground">
              {t("Every account has its own profile and data — nothing is shared between accounts.")}
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
