import { useRef, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  BriefcaseBusiness,
  Eye,
  EyeOff,
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

function authError(err: unknown, registering: boolean): string {
  if (err instanceof ApiError) {
    if (err.status === 0 || err.status >= 500) return "مش قادرين نوصل للسيرفر دلوقتي. جرّب تاني بعد شوية.";
    if (err.status === 401) return "رقم الموبايل أو كلمة السر مش صح. راجعهم وجرّب تاني.";
    if (err.status === 409 && registering) return "رقم الموبايل ده عليه حساب بالفعل. جرّب تدخل لحسابك.";
    if (err.status === 400 || err.status === 422) {
      return "راجع البيانات ورقم الموبايل. كلمة السر لازم تكون من ٦ لـ١٢٨ حرف.";
    }
    if (err.status === 429) return "محاولات كتير في وقت قصير. استنى شوية وجرّب تاني.";
  }
  return "مقدرناش نكمّل الطلب. جرّب تاني.";
}

export function LoginPage() {
  const { user, login, register, busy } = useAuth();
  const { toast } = useToast();
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
      setError("اكتب اسمك بالكامل.");
      return;
    }
    if (!phone) {
      setError("اكتب رقم موبايلك.");
      return;
    }
    if (!PHONE_RE.test(phone)) {
      setError("رقم الموبايل أرقام بس — اكتبه زي 01xxxxxxxxx أو +20xxxxxxxxxx.");
      return;
    }
    if (password.length < 6 || password.length > 128) {
      setError("كلمة السر لازم تكون من ٦ لـ١٢٨ حرف.");
      return;
    }
    if (registering && password !== confirmation) {
      setError("تأكيد كلمة السر مش مطابق. اكتب نفس كلمة السر تاني.");
      return;
    }
    submitting.current = true;
    setPending(true);
    try {
      const credentials = { phone: phone.trim(), password };
      if (registering) {
        await register({ ...credentials, full_name: fullName.trim() });
        navigate("/profile", { replace: true });
        toast("حسابك اتعمل! كمّل مهاراتك وارفع الـCV، وبعدها ابدأ بـ Import.");
      } else {
        await login(credentials);
        navigate("/", { replace: true });
      }
      setPassword("");
      setConfirmation("");
    } catch (err) {
      setError(authError(err, registering));
      setPassword("");
      setConfirmation("");
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  if (user) return <Navigate to="/" replace />;

  return (
    <main dir="rtl" lang="ar" className="relative min-h-screen bg-background">
      <div className="grid grid-cols-1 min-h-screen lg:grid-cols-[1.02fr_1fr]">
        <section className="relative hidden flex-col justify-between overflow-hidden bg-primary p-10 text-primary-foreground lg:flex xl:p-14">
          <div className="surface-grid absolute inset-0 opacity-40" aria-hidden />
          <div className="relative flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-foreground text-primary shadow-lift">
              <BriefcaseBusiness className="h-5 w-5" />
            </div>
            <div>
              <p className="text-lg font-bold leading-tight tracking-tight" dir="ltr">JobHunter</p>
              <p className="text-xs text-primary-foreground/70">AI job-search desk</p>
            </div>
          </div>

          <div className="relative max-w-lg space-y-8">
            <div className="space-y-4">
              <p className="text-xs font-medium text-primary-foreground/60">مكتبك الشخصي للبحث عن شغل</p>
              <h1 className="text-4xl font-bold leading-[1.25] xl:text-[44px]">
                وظيفتك الجاية
                <br />
                تبدأ من هنا.
              </h1>
              <p className="max-w-md text-sm leading-relaxed text-primary-foreground/75">
                كل الوظائف الحقيقية في مكان واحد، وملفك هو الأساس لكل حاجة بنكتبها لك — مفيش كلام متألّف ولا بيانات من عندنا.
              </p>
            </div>

            <ul className="space-y-4">
              {[
                { icon: Sparkles, title: "بحث حقيقي ومرتّب", text: "وظايف من مصادر عامة حقيقية، من غير إعلانات وهمية." },
                { icon: ShieldCheck, title: "بياناتك ملكك", text: "كل حساب ليه ملفه ووظايفه، ومفيش حد بيشوف التاني." },
                { icon: Send, title: "مفيش إرسال أوتوماتيك", text: "بنكتب السيفي والرسالة، وانت اللي بتراجع وتبعت." },
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
            نسخة محلية — البيانات على جهازك، والسيرفر لازم يكون شغّال.
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
                <p className="text-[11px] text-muted-foreground">AI job-search desk</p>
              </div>
            </div>

            <div className="rounded-xl border border-border/80 bg-card p-6 shadow-lift sm:p-8">
              <div className="space-y-1.5">
                <h2 className="text-2xl font-bold tracking-tight">
                  {registering ? "اعمل حساب جديد" : "أهلاً بيك تاني"}
                </h2>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {registering
                    ? "برقم موبايلك وكلمة سر بسيطة، عشان تبدأ فورًا."
                    : "ادخل لحسابك وكمّل من آخر حاجة وقفت عندها."}
                </p>
              </div>

              <div className="mt-6 grid grid-cols-2 gap-1.5 rounded-xl border border-border/70 bg-muted/60 p-1" aria-label="اختار الدخول أو إنشاء حساب">
                {[
                  { value: "login" as const, label: "دخول" },
                  { value: "register" as const, label: "حساب جديد" },
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
                onInvalidCapture={() => setError("راجع البيانات المطلوبة. كلمة السر لازم تكون من ٦ لـ١٢٨ حرف.")}
              >
                <fieldset disabled={disabled} className="space-y-4">
                  {registering && (
                    <div className="space-y-1.5">
                      <Label htmlFor="auth-name">الاسم بالكامل</Label>
                      <div className="relative">
                        <UserRound className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          id="auth-name"
                          name="full_name"
                          autoComplete="name"
                          required
                          className="h-11 pr-10"
                          value={fullName}
                          onChange={(event) => { setFullName(event.target.value); setError(null); }}
                        />
                      </div>
                    </div>
                  )}

                  <div className="space-y-1.5">
                    <Label htmlFor="auth-phone">رقم الموبايل</Label>
                    <div className="relative">
                      <Phone className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        id="auth-phone"
                        name="phone"
                        type="tel"
                        inputMode="tel"
                        autoComplete="tel"
                        dir="ltr"
                        required
                        maxLength={16}
                        className="h-11 pr-10 text-left"
                        placeholder="01xxxxxxxxx"
                        value={phone}
                        onChange={(event) => { setPhone(sanitizePhone(event.target.value)); setError(null); }}
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="auth-password">كلمة السر</Label>
                    <div className="relative">
                      <Lock className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
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
                        className="h-11 pl-11 pr-10"
                        value={password}
                        onChange={(event) => { setPassword(event.target.value); setError(null); }}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((v) => !v)}
                        className="absolute left-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                        aria-label={showPassword ? "إخفاء كلمة السر" : "إظهار كلمة السر"}
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    <p id="auth-password-help" className="text-[11px] text-muted-foreground">من ٦ لـ١٢٨ حرف.</p>
                  </div>

                  {registering && (
                    <div className="space-y-1.5">
                      <Label htmlFor="auth-confirmation">تأكيد كلمة السر</Label>
                      <div className="relative">
                        <ShieldCheck className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
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
                          className="h-11 pr-10"
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
                    {disabled ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <ArrowLeft className="h-4 w-4" aria-hidden="true" />}
                    {disabled ? "استنى لحظة…" : registering ? "اعمل حسابك وابدأ" : "ادخل لحسابك"}
                  </Button>
                </fieldset>
              </form>
            </div>

            <p className="mt-6 text-center text-[11px] leading-relaxed text-muted-foreground">
              كل حساب ليه ملفه وبياناته الخاصة — مفيش مشاركة بين الحسابات.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
