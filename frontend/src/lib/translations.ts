// English UI strings → Modern Standard Arabic. The UI renders the English key itself
// when no entry exists, so a missing translation degrades gracefully, never to an error.
export const AR: Record<string, string> = {  // topbar
  Workspace: "مساحة العمل",
  Dashboard: "الرئيسية",
  "AI Matches": "المطابقات بالذكاء الاصطناعي",
  "AI Assistant": "المساعد الذكي",
  "Resume & Profile": "السيرة الذاتية والملف الشخصي",
  Connecting: "جارٍ الاتصال",
  "All systems ready": "جميع الأنظمة جاهزة",
  "Backend offline": "الخادم غير متاح",
  "Checking the backend": "جارٍ التحقق من الخادم",
  "Backend connected": "متصل بالخادم",
  "Backend offline — check your connection": "الخادم غير متاح — تحقق من اتصالك",
  "Open menu": "فتح القائمة",
  "Switch to light mode": "التبديل إلى الوضع الفاتح",
  "Switch to dark mode": "التبديل إلى الوضع الداكن",
  "Light mode": "الوضع الفاتح",
  "Dark mode": "الوضع الداكن",
  English: "الإنجليزية",
  "Switch language": "تغيير اللغة",

  // sidebar
  Discover: "استكشاف",
  "Your AI job-search desk": "مكتبك للبحث عن العمل بالذكاء الاصطناعي",
  "Close menu": "إغلاق القائمة",
  "Personal workspace": "مساحتك الشخصية",
  "Sign out": "تسجيل الخروج",
  "Private to your account. Jobs come from real public sources.":
    "خاص بحسابك. الوظائف تأتي من مصادر عامة حقيقية.",
  "Couldn't confirm sign-out. Your account is still open here — try again.":
    "تعذّر تأكيد تسجيل الخروج. حسابك ما زال مفتوحًا هنا — حاول مرة أخرى.",

  // login / register
  "We can't reach the server right now. Try again in a bit.":
    "يتعذّر الوصول إلى الخادم الآن. حاول مرة أخرى بعد قليل.",
  "The phone number or password is wrong. Check them and try again.":
    "رقم الهاتف أو كلمة المرور غير صحيح. تحقق منهما وحاول مرة أخرى.",
  "This phone number already has an account. Try logging in.":
    "رقم الهاتف هذا مسجّل بحساب بالفعل. حاول تسجيل الدخول.",
  "Check your details and phone number. The password must be 6–128 characters.":
    "تحقق من بياناتك ورقم هاتفك. يجب أن تتكون كلمة المرور من 6 إلى 128 حرفًا.",
  "Too many attempts in a short time. Wait a bit and try again.":
    "محاولات كثيرة في وقت قصير. انتظر قليلًا وحاول مرة أخرى.",
  "We couldn't complete the request. Try again.": "تعذّر إكمال الطلب. حاول مرة أخرى.",
  "Write your full name.": "اكتب اسمك الكامل.",
  "Write your phone number.": "اكتب رقم هاتفك.",
  "The phone number is digits only — write it like 01xxxxxxxxx or +20xxxxxxxxxx.":
    "رقم الهاتف يتكون من أرقام فقط — اكتبه على النحو التالي: 01xxxxxxxxx أو +20xxxxxxxxxx.",
  "The password must be 6–128 characters.": "يجب أن تتكون كلمة المرور من 6 إلى 128 حرفًا.",
  "The password confirmation doesn't match. Write the same password again.":
    "تأكيد كلمة المرور غير مطابق. اكتب كلمة المرور نفسها مرة أخرى.",
  "Your account is ready! Complete your skills and upload your CV, then start with Import.":
    "حسابك جاهز! أكمل مهاراتك وارفع سيرتك الذاتية، ثم ابدأ بالاستيراد.",
  "Your personal job-search desk": "مكتبك الشخصي للبحث عن العمل",
  "Your next job": "وظيفتك القادمة",
  "starts here.": "تبدأ من هنا.",
  "Every real job in one place, and your profile is the basis for everything we write for you — no invented words, no made-up data.":
    "كل وظيفة حقيقية في مكان واحد، وملفك الشخصي هو الأساس لكل ما نكتبه لك — لا كلمات مختلقة ولا بيانات مُفبركة.",
  "Real, organised search": "بحث حقيقي ومنظّم",
  "Jobs from real public sources — no fake listings.":
    "وظائف من مصادر عامة حقيقية — لا إعلانات وهمية.",
  "Your data is yours": "بياناتك ملكك",
  "Every account has its own profile and jobs — nobody sees anyone else's.":
    "لكل حساب ملفه الشخصي ووظائفه — لا يرى أحد بيانات غيره.",
  "No auto-sending": "لا إرسال تلقائي",
  "We write the CV and message; you review and send.":
    "نكتب السيرة الذاتية والرسالة، وأنت تراجعها وترسلها.",
  "Your own account — your data is isolated and nobody else can see it.":
    "حسابك الخاص — بياناتك معزولة ولا يطّلع عليها أحد غيرك.",
  "Create a new account": "إنشاء حساب جديد",
  "Welcome back": "مرحبًا بعودتك",
  "With your phone number and a simple password, so you can start right away.":
    "برقم هاتفك وكلمة مرور بسيطة، لتبدأ فورًا.",
  "Log in to your account and continue where you left off.":
    "سجّل الدخول إلى حسابك وأكمل من حيث توقفت.",
  "Choose login or sign-up": "اختر تسجيل الدخول أو إنشاء حساب",
  "Log in": "تسجيل الدخول",
  "Sign up": "حساب جديد",
  "Check the required details. The password must be 6–128 characters.":
    "تحقق من البيانات المطلوبة. يجب أن تتكون كلمة المرور من 6 إلى 128 حرفًا.",
  "Full name": "الاسم الكامل",
  "Phone number": "رقم الهاتف",
  Password: "كلمة المرور",
  "Hide password": "إخفاء كلمة المرور",
  "Show password": "إظهار كلمة المرور",
  "6–128 characters.": "من 6 إلى 128 حرفًا.",
  "Confirm password": "تأكيد كلمة المرور",
  "One moment…": "لحظة واحدة…",
  "Create your account and start": "أنشئ حسابك وابدأ",
  "Log in to your account": "تسجيل الدخول إلى حسابك",
  "Every account has its own profile and data — nothing is shared between accounts.":
    "لكل حساب ملفه وبياناته الخاصة — لا شيء مشترك بين الحسابات.",

  // auth guard screen
  "Checking your account…": "جارٍ التحقق من حسابك…",
  "Waking the server": "جارٍ تشغيل الخادم",
  "The first visit after a quiet spell starts the server — it can take up to a minute.":
    "أول زيارة بعد فترة خمول تشغّل الخادم، وقد يستغرق ذلك حتى دقيقة.",
  "Can't reach the server": "تعذّر الاتصال بالخادم",
  "We can't confirm your account right now. Check your connection, then try again.":
    "تعذّر التحقق من حسابك الآن. تحقق من اتصالك ثم حاول مرة أخرى.",
  "Try again": "إعادة المحاولة",

  // dropped or slow connections
  Loading: "جارٍ التحميل",
  "The server took too long to answer. Check your connection and try again.":
    "استغرق الخادم وقتًا طويلًا دون استجابة. تحقق من اتصالك وحاول مرة أخرى.",
  "The server is starting up — try again in a moment.":
    "الخادم قيد التشغيل — حاول مرة أخرى بعد لحظة.",
  "The server is busy — try again in a moment.":
    "الخادم مشغول — حاول مرة أخرى بعد لحظة.",

  // shared states
  "Loading this page": "جارٍ تحميل الصفحة",
  "This could not be loaded": "تعذّر تحميل هذا المحتوى",
  Retry: "إعادة المحاولة",
  "This page hit an error": "حدث خطأ في هذه الصفحة",
  "Your saved data is safe. Reload to continue — if it keeps happening, restart the backend too.":
    "بياناتك المحفوظة سليمة. أعد تحميل الصفحة للمتابعة — وإذا تكرر ذلك، أعد تشغيل الخادم أيضًا.",
  Reload: "إعادة التحميل",

  // server answers shown as they arrive, so they need an Arabic line too
  "Cannot reach the server. Check your connection and try again.":
    "تعذّر الوصول إلى الخادم. تحقق من اتصالك وحاول مرة أخرى.",
  "An application for this job already exists": "يوجد تقديم مسجّل لهذه الوظيفة بالفعل",
  "Application not found": "التقديم غير موجود",
  "Job not found": "الوظيفة غير موجودة",
  "Material not found": "المستند غير موجود",
  "This document has not been prepared yet": "لم يتم إعداد هذا المستند بعد",
  "Authentication required": "يجب تسجيل الدخول أولًا",
  "Authentication request is too large": "بيانات تسجيل الدخول أكبر من المسموح",
  "Request origin is not allowed": "مصدر الطلب غير مسموح به",
  "X-Requested-With: XMLHttpRequest is required": "يجب أن يصدر الطلب من التطبيق نفسه",
  "This phone number is already registered": "رقم الهاتف هذا مسجّل بالفعل",
  "Invalid phone or password": "رقم الهاتف أو كلمة المرور غير صحيح",
  "Too many authentication attempts. Try again later.":
    "محاولات دخول كثيرة متتالية. انتظر قليلًا ثم حاول مرة أخرى.",
  "Upload a resume with readable text first — there is nothing to read.":
    "ارفع سيرة ذاتية تحتوي على نص مقروء أولًا — لا يوجد ما يمكن قراءته.",
  "Skill name cannot be empty": "لا يمكن أن يكون اسم المهارة فارغًا",
  "Each skill needs a name and an optional level (1-5)":
    "تحتاج كل مهارة إلى اسم ومستوى اختياري (1-5)",
  "Skill years must be a number between 0 and 60": "يجب أن تكون سنوات الخبرة في المهارة عددًا بين 0 و60",
  "Expected a JSON object": "يجب أن تكون البيانات على هيئة كائن JSON صحيح",
  "Internal server error": "حدث خطأ داخلي في الخادم",
  "Server is busy, retry shortly": "الخادم مشغول الآن، أعد المحاولة بعد قليل",
  "The database is unavailable. Retry shortly.": "قاعدة البيانات غير متاحة حاليًا. أعد المحاولة بعد قليل.",
  "Too many requests. Wait a moment and try again.": "طلبات كثيرة في وقت قصير. انتظر لحظة ثم أعد المحاولة.",
  "Request body is too large": "حجم البيانات المرسلة أكبر من المسموح.",
  "A generation is already running. Wait a moment.": "هناك عملية توليد قيد التنفيذ بالفعل. انتظر لحظة.",
  "This application is already at {stage}": "هذا التقديم في مرحلة {stage} بالفعل",
  "An authentication request is already in progress.": "هناك محاولة دخول قيد التنفيذ الآن، انتظر حتى تنتهي.",
  "The backend did not confirm logout.": "لم يؤكد الخادم تسجيل الخروج.",

  // dates & salaries
  "Not disclosed": "غير معلن",
  "up to": "حتى",
  "just now": "الآن",
  "{mins}m ago": "قبل {mins} دقيقة",
  "{hours}h ago": "قبل {hours} ساعة",
  "{days}d ago": "قبل {days} يوم",
  "{months}mo ago": "قبل {months} شهر",
  "{years}y ago": "قبل {years} سنة",
  Posted: "نُشرت",
  Listed: "أُضيفت",
  "{word} today": "{word} اليوم",
  "{word} yesterday": "{word} أمس",
  "{word} {days}d ago": "{word} قبل {days} يوم",
  "{word} {ago}": "{word} {ago}",
  "In your tracker since {date}": "في متابعتك منذ {date}",
  "Date not stated": "التاريخ غير مذكور",

  // job statuses
  Discovered: "مكتشفة",
  Interested: "مهتم بها",
  Preparing: "قيد الإعداد",
  Applied: "تم التقديم",
  Interview: "مقابلة",
  Offer: "عرض عمل",
  Rejected: "مرفوضة",
  Archived: "مؤرشفة",
  "Imported from {source}": "مستوردة من {source}",

  // job cards & detail
  "Type n/a": "النوع غير متاح",
  "Level n/a": "المستوى غير متاح",
  Remote: "عن بُعد",
  "No longer advertised": "لم تعد معلنة",
  "View details": "عرض التفاصيل",
  Track: "تابع",
  "Save job": "حفظ الوظيفة",
  "Removed from saved jobs": "أُزيلت من الوظائف المحفوظة",
  "Job saved": "تم حفظ الوظيفة",
  "CV PDF saved — the tailored copy, without the red marks":
    "تم حفظ CV PDF — النسخة المخصصة، دون العلامات الحمراء",
  "Type not specified": "النوع غير محدد",
  "Level not specified": "المستوى غير محدد",
  "No longer advertised by {board}": "لم تعد معلنة على {board}",
  Salary: "الراتب",
  "via {source}": "عبر {source}",
  "Expires {date}": "ينتهي في {date}",
  "Not stated": "غير مذكور",
  "AI match estimate": "تقدير التطابق بالذكاء الاصطناعي",
  "Match unavailable — the server could not score this job. Try again in a moment.":
    "التطابق غير متاح — تعذّر على الخادم تقييم هذه الوظيفة. حاول مرة أخرى بعد قليل.",
  "Calculating…": "جارٍ الحساب…",
  "Estimate based on your profile — not a guarantee.": "تقدير مبني على ملفك الشخصي — وليس ضمانًا.",
  "You have": "لديك",
  "Missing / weak": "مفقود / ضعيف",
  "Writing your pack…": "جارٍ كتابة حزمة التقديم…",
  "Prepare the application pack": "إعداد حزمة التقديم",
  "Download CV PDF": "تنزيل CV PDF",
  "Open this ad": "فتح هذا الإعلان",
  "I applied to this": "لقد تقدمت لهذه الوظيفة",
  "I have not actually applied yet": "لم أتقدّم فعليًا بعد",
  "Marked as applied": "تم تحديدها كمقدَّم عليها",
  "Applied mark removed": "أُزيلت علامة التقديم",
  "Applied mark removed — the pack stays in your desk": "أُزيلت علامة التقديم — وتبقى حزمة التقديم في لوحتك",
  "Still {stage} in your desk": "لا تزال {stage} في لوحتك",
  "This stage comes from your Applications Desk": "هذه المرحلة من لوحة التقديمات — غيّرها من هناك",
  "One document in Assistant": "مستند واحد في المساعد",
  Saved: "محفوظة",
  Save: "حفظ",

  // apply route
  "Company page": "صفحة الشركة",
  "Board page": "صفحة الإعلان",
  "How to apply": "طريقة التقديم",
  "Open the mail draft": "فتح مسودة البريد الإلكتروني",
  "Open the company page": "فتح صفحة الشركة",
  "Apply on {board}": "التقديم على {board}",
  "Copy this address": "نسخ هذا العنوان",
  "Open this page": "فتح هذه الصفحة",
  "Address": "العنوان",
  "{what} copied": "تم نسخ {what}",
  "Could not copy — select it manually": "تعذّر النسخ — حدده يدويًا ثم انسخه",
  "Read from the ad itself. Nothing leaves this app: the mail draft only opens in your own program, and you press send.":
    "مقروءة من الإعلان نفسه. لا شيء يخرج من هذا التطبيق: تُفتح مسودة البريد في برنامجك أنت فقط، وأنت من يضغط إرسال.",

  // application pack
  "Application pack": "حزمة التقديم",
  "The pack was rebuilt from what your profile holds today": "أُعيد بناء الحزمة من بيانات ملفك الشخصي الحالية",
  "Copied to clipboard": "تم النسخ إلى الحافظة",
  "Could not copy — select the text and copy manually": "تعذّر النسخ — حدد النص وانسخه يدويًا",
  "Nothing has been prepared for this ad yet.": "لم يُعدّ شيء لهذا الإعلان بعد.",
  "Prepare CV, letter, email and questions": "إعداد السيرة الذاتية والخطاب والبريد والأسئلة",
  "Download a CV PDF written for this ad, built only from your profile":
    "تنزيل CV PDF مكتوبة لهذا الإعلان، مبنية من ملفك الشخصي فقط",
  "Template draft": "مسودة قالب",
  "AI draft": "مسودة ذكاء اصطناعي",
  "Written {date}": "كُتبت في {date}",
  "{count} added for this ad — confirm them": "{count} إضافات لهذا الإعلان — تحقق منها",
  Copy: "نسخ",
  "Download the copy you check before sending — additions the assistant suggested are printed in red":
    "نزّل النسخة التي تراجعها قبل الإرسال — الإضافات التي اقترحها المساعد مطبوعة بالأحمر",
  "CV PDF with red marks": "CV PDF بالعلامات الحمراء",
  "Download the copy for the employer — the red marks are gone and the added lines stay as normal text":
    "نزّل النسخة المخصصة لصاحب العمل — أُزيلت العلامات الحمراء وبقيت السطور المضافة نصًا عاديًا",
  "Clean CV PDF": "CV PDF نظيفة",
  "Save .md": "حفظ .md",
  Rebuild: "إعادة البناء",
  "This document came back empty — rebuild the pack.": "عاد هذا المستند فارغًا — أعد بناء الحزمة.",
  "— these are the lines the assistant added above. Check every one you cannot back up before the clean copy goes out — it prints them in black.":
    "— هذه هي السطور التي أضافها المساعد أعلاه. راجع كل سطر لا تستطيع إثباته قبل إخراج النسخة النظيفة — إذ تطبعها بالأسود.",
  "Every line without a red mark comes straight from what you entered in":
    "كل سطر دون علامة حمراء يأتي مباشرة مما كتبته في",
  ". Red lines are the assistant's additions for this ad; the clean PDF prints them in black without the marks. The CV is rebuilt for ATS parsers — standard headings, plain single-column text — and the readiness score is at the bottom of this review. Read it, confirm what you can back up, then apply yourself — nothing here is sent for you.":
    ". السطور الحمراء إضافات المساعد لهذا الإعلان، ويطبعها الـPDF النظيف بالأسود دون العلامات. تُعاد السيرة الذاتية بناءً لتناسب أنظمة فحص ATS — عناوين قياسية ونص عادي بعمود واحد — ويظهر تقرير الجاهزية في أسفل هذه المراجعة. اقرأها، وتحقّق مما تستطيع إثباته، ثم قدّم بنفسك — لا شيء هنا يُرسل عنك.",
  "{count} documents prepared for this ad": "تم إعداد {count} مستند لهذا الإعلان",
  "{count} docs": "{count} مستندات",
  "Write the CV, letter, email, questions and keywords for this ad":
    "كتابة السيرة الذاتية والخطاب والبريد والأسئلة والكلمات المفتاحية لهذا الإعلان",
  Prepare: "إعداد",

  // document tabs
  "Tailored CV": "سيرة ذاتية مخصصة",
  "Cover letter": "خطاب تقديم",
  "Application email": "بريد التقديم",
  "Interview questions": "أسئلة المقابلة",
  "Keywords from the ad": "كلمات مفتاحية من الإعلان",
  "Resume summary": "ملخص السيرة",
  "Resume bullets": "نقاط السيرة",
  "Cover Letter": "خطاب التقديم",
  "Application Email": "بريد التقديم",
  "Interview Questions": "أسئلة المقابلة",
  Keywords: "كلمات مفتاحية",

  // find jobs page
  "Job database": "قاعدة بيانات الوظائف",
  "Find Jobs": "البحث عن وظائف",
  "Searching your job database…": "جارٍ البحث في قاعدة بيانات الوظائف…",
  "Show pulled postings": "عرض الإعلانات المسحوبة",
  "Import jobs": "استيراد الوظائف",
  "One site at a time keeps each server light — the number is how many live postings that site has given you so far.":
    "استيراد موقع واحد في كل مرة يبقي الضغط خفيفًا على كل خادم — والرقم هو عدد الوظائف المتاحة التي وفّرها لك هذا الموقع حتى الآن.",
  "Press a site to import it alone, or a region button to import every site covering that region. The number is how many live postings that site has given you so far.":
    "اضغط على موقع لاستيراده وحده، أو على زر منطقة لاستيراد جميع المواقع التي تغطيها. والرقم هو عدد الوظائف المتاحة التي وفّرها لك ذلك الموقع حتى الآن.",
  "{n} sites to pull from — press a region to import it all at once, or open the list to choose a single site":
    "{n} موقعًا متاحًا للاستيراد — اضغط على منطقة لاستيرادها دفعة واحدة، أو افتح القائمة لاختيار موقع واحد.",
  "Open the site list": "فتح قائمة المواقع",
  "Fold the site list": "إغلاق قائمة المواقع",
  "Importing…": "جارٍ الاستيراد…",
  "Import Egypt jobs": "استيراد وظائف داخل مصر",
  "Import jobs outside Egypt": "استيراد وظائف خارج مصر",
  "Egypt jobs": "وظائف داخل مصر",
  "jobs outside Egypt": "وظائف خارج مصر",
  "Searches every source that lists jobs inside Egypt, in one run":
    "يبحث في كل المصادر التي تعرض وظائف داخل مصر، في عملية واحدة.",
  "Searches every source that lists jobs outside Egypt, in one run":
    "يبحث في كل المصادر التي تعرض وظائف خارج مصر، في عملية واحدة.",
  "No importable sites are available for this region.": "لا توجد مواقع استيراد متاحة لهذه المنطقة.",
  "Unknown region. Choose egypt or worldwide.": "منطقة غير معروفة. القيم المتاحة: egypt أو worldwide.",
  "Import all ticked sites": "استيراد كل المواقع المحددة",
  "all ticked sources": "كل المصادر المحددة",
  "import only from this site": "استيراد من هذا الموقع فقط",
  "needs a key": "يتطلب مفتاحًا",
  "{n} live": "{n} متاحة",
  "nothing new last run": "لا جديد في آخر تشغيل",
  "not imported yet": "لم يُستورد بعد",
  "The site list did not load: {error}.": "تعذّر تحميل قائمة المواقع: {error}.",
  "Loading the site list…": "جارٍ تحميل قائمة المواقع…",
  "Starting the import…": "جارٍ بدء الاستيراد…",
  "Importing from {label} — site {done} of {total}": "جارٍ الاستيراد من {label} — الموقع {done} من {total}",
  "Every import searches for your saved titles, skills and locations (Automation settings), then hides postings older than your max job age.":
    "كل استيراد يبحث عن المسميات والمهارات والمواقع المحفوظة لديك (إعدادات الأتمتة)، ثم يخفي الإعلانات الأقدم من أقصى عمر تحدده للإعلان.",
  "Sites that post Egypt jobs but publish no import feed":
    "مواقع تنشر وظائف مصرية لكنها لا توفر تغذية استيراد",
  "These block automated access, so the app will not pretend to import them. One click opens your own search there:":
    "هذه المواقع تمنع الوصول الآلي، لذا لا يدّعي التطبيق الاستيراد منها. ضغطة واحدة تفتح بحثك الخاص عليها:",
  "Inside Egypt": "داخل مصر",
  "Outside Egypt": "خارج مصر",
  "{sites} sites · {jobs} live": "{sites} من المواقع · {jobs} وظيفة متاحة",
  "Filters": "عوامل التصفية",
  "Clear all": "مسح الكل",
  "Search": "بحث",
  "Title, company or description…": "المسمى أو الشركة أو الوصف…",
  "e.g. Flutter": "مثال: Flutter",
  "Location": "الموقع",
  "All levels": "جميع المستويات",
  "Employment type": "نوع التوظيف",
  "All types": "جميع الأنواع",
  "Source": "المصدر",
  "All sources": "جميع المصادر",
  "Work mode": "نمط العمل",
  "Onsite & remote": "حضوري وعن بُعد",
  "Sort by": "الترتيب حسب",
  "Newest first": "الأحدث أولًا",
  "Title A–Z": "المسمى أ–ي",
  "Company A–Z": "الشركة أ–ي",
  "Highest salary": "الأعلى راتبًا",
  "Active:": "مفعّل:",
  "Skill: {skill}": "مهارة: {skill}",
  "Location: {location}": "موقع: {location}",
  "{label}: {count} new job imported": "{label}: تم استيراد {count} وظيفة جديدة",
  "{label}: {count} new jobs imported": "{label}: تم استيراد {count} وظيفة جديدة",
  "{label}: nothing new — every live posting is already in your database":
    "{label}: لا جديد — كل إعلان متاح موجود بالفعل في قاعدة بياناتك",
  "{count} postings match your filters": "{count} إعلان مطابق لعوامل التصفية",
  "{count} live postings match your filters": "{count} وظيفة متاحة مطابقة لعوامل التصفية",
  "{count} postings on {source} match your filters": "{count} إعلان مطابق لعوامل التصفية على {source}",
  "{count} live postings on {source} match your filters": "{count} وظيفة متاحة مطابقة لعوامل التصفية على {source}",
  "{count} postings in your database": "{count} إعلان في قاعدة بياناتك",
  "{count} live postings in your database": "{count} وظيفة متاحة في قاعدة بياناتك",
  " · {count} live across all sites": " · {count} متاحة على جميع المواقع",
  "{error} — showing the last results that loaded.": "{error} — يتم عرض آخر النتائج التي حُمّلت.",
  "No jobs found": "لا توجد وظائف",
  "Try different filters, or import from one of the sites above to fill your database.":
    "جرّب عوامل تصفية مختلفة، أو استورد من أحد المواقع أعلاه لملء قاعدة بياناتك.",
  "Import jobs now": "استيراد الوظائف الآن",
  "Showing": "يُعرض",
  "of": "من",
  "— use “Load more” to keep browsing.": "— استخدم «تحميل المزيد» لمتابعة التصفح.",
  "Load more ({n} more)": "تحميل المزيد ({n} إضافية)",
  "Added to the Applications Desk": "أُضيفت إلى لوحة التقديمات",

  // matches page
  "Ranking": "الترتيب",
  "AI Job Matches": "تطابقات الوظائف بالذكاء الاصطناعي",
  "Transparent match estimates (0–100) computed from your profile. Best fit first; inside the same score the freshest posting wins. Scores are estimates, not guarantees.":
    "تقديرات تطابق واضحة (0–100) تُحسب من ملفك الشخصي. الأنسب أولًا؛ وعند تساوي الدرجة، يفوز الإعلان الأحدث. الدرجات تقديرات وليست ضمانات.",
  "Your profile is empty": "ملفك الشخصي فارغ",
  "Every score is 0 until you add your skills.": "كل الدرجات صفر حتى تضيف مهاراتك.",
  "Go to Profile": "الانتقال إلى الملف الشخصي",
  "Filter matches by title or company": "تصفية التطابقات حسب المسمى أو الشركة",
  "Filter by title or company…": "تصفية حسب المسمى أو الشركة…",
  "Min score": "أدنى درجة",
  "Any": "أي درجة",
  "Top {n} of {total}": "أفضل {n} من {total}",
  "{total} scored": "تم تقييم {total}",
  "No matches at this threshold": "لا توجد تطابقات عند هذا الحد",
  "Lower the minimum score or complete your profile to get better matches.":
    "اخفض الحد الأدنى للدرجة أو أكمل ملفك الشخصي للحصول على تطابقات أفضل.",
  "match": "تطابق",
  "Open the full posting and its apply link": "فتح الإعلان كاملًا ورابط التقديم",
  "AI enhanced": "مدعوم بالذكاء الاصطناعي",
  "level n/a": "المستوى غير مذكور",
  "Apply": "تقديم",
  "Why this score?": "لماذا هذه الدرجة؟",
  "Assistant": "المساعد",
  "match breakdown": "تفصيل التطابق",
  "How the estimate was calculated": "كيفية حساب التقدير",
  "Deterministic scoring from your profile. Treat as an estimate.":
    "تقييم ثابت يُحسب من ملفك الشخصي. تعامل معه كتقدير.",
  "Why it matches:": "لماذا يتطابق:",
  "Concerns:": "ملاحظات للانتباه:",
  "Suggested next steps": "الخطوات المقترحة التالية",
  "Open the full posting": "فتح الإعلان كاملًا",

  // saved jobs page
  "Shortlist": "القائمة المختصرة",
  "Saved Jobs": "الوظائف المحفوظة",
  "Jobs you bookmarked for later — review them, prep the application, and apply when you are ready.":
    "وظائف حفظتها لوقت لاحق — راجعها، وجهّز التقديم، وقدّم عندما تكون مستعدًا.",
  "Filter saved jobs": "تصفية الوظائف المحفوظة",
  "Filter saved jobs…": "تصفية الوظائف المحفوظة…",
  "No saved jobs match your filter": "لا توجد وظائف محفوظة مطابقة لعوامل التصفية",
  "No saved jobs yet": "لا توجد وظائف محفوظة بعد",
  "Try a different filter.": "جرّب عامل تصفية مختلفًا.",
  "Browse Find Jobs and bookmark interesting roles to see them here.":
    "تصفّح صفحة «البحث عن وظائف» واحفظ الأدوار التي تهمك لتظهر هنا.",
  "Find jobs": "البحث عن وظائف",
  "Estimated match score from your profile — not a guarantee":
    "درجة تطابق تقديرية من ملفك الشخصي — ليست ضمانًا",
  "Remove from saved": "إزالة من المحفوظة",
  "Remove": "إزالة",

  // applications page
  "Prepared {n} documents for this ad": "تم إعداد {n} مستند لهذا الإعلان",
  "Status changed to {status}": "تم تغيير الحالة إلى {status}",
  "Application deleted": "تم حذف التقديم",
  "Status for {title}": "حالة {title}",
  "Pipeline": "مسار التقديم",
  "Applications Desk": "لوحة التقديمات",
  "Press Prepare and the AI writes the CV, letter, email, questions and keywords for that one ad. You read them, you send them — nothing goes out on its own.":
    "اضغط «إعداد» فيكتب الذكاء الاصطناعي السيرة الذاتية والخطاب والبريد والأسئلة والكلمات المفتاحية لهذا الإعلان. أنت تقرؤها وأنت ترسلها — لا شيء يُرسل من تلقاء نفسه.",
  "Filter applications by status": "تصفية التقديمات حسب الحالة",
  "All statuses": "جميع الحالات",
  "Table": "جدول",
  "Kanban": "لوحة",
  'No applications with status "{status}"': 'لا توجد تقديمات بالحالة "{status}"',
  "No applications tracked yet": "لا توجد تقديمات متابعة بعد",
  "Clear the status filter to see all of your tracked applications.":
    "امسح عامل تصفية الحالة لعرض جميع تقديماتك المتابعة.",
  "Use the Track button on any job in Find Jobs to start tracking it here.":
    "استخدم زر «تابع» على أي وظيفة في صفحة البحث عن وظائف لبدء متابعتها هنا.",
  "Show all statuses": "عرض جميع الحالات",
  "Find jobs to track": "ابحث عن وظائف لتتابعها",
  "Job": "الوظيفة",
  "Status": "الحالة",
  "AI pack": "حزمة الذكاء الاصطناعي",
  "Timeline": "الجدول الزمني",
  "Notes": "ملاحظات",
  "Actions": "إجراءات",
  "Follow-up": "متابعة",
  "Open job posting": "فتح إعلان الوظيفة",
  "Write one document yourself in the Assistant": "اكتب مستندًا واحدًا بنفسك في المساعد",
  "Edit": "تعديل",
  "Delete": "حذف",
  "Empty": "فارغ",
  "Delete application": "حذف التقديم",
  'Remove the application for "{title}"? This cannot be undone.':
    'هل تريد حذف تقديم "{title}"؟ لا يمكن التراجع عن هذه الخطوة.',
  "Application updated": "تم تحديث التقديم",
  "Date applied": "تاريخ التقديم",
  "Follow-up date": "تاريخ المتابعة",
  "Interview date": "تاريخ المقابلة",
  "Contacts, salary expectations, interview feedback…":
    "جهات الاتصال، توقعات الراتب، ملاحظات المقابلة…",
  "Cancel": "إلغاء",
  "Saving…": "جارٍ الحفظ…",
  "Save changes": "حفظ التغييرات",

  // assistant page
  "Select a job first": "اختر وظيفة أولًا",
  "Material deleted": "تم حذف المستند",
  "Review copy saved — the lines the assistant added are printed in red":
    "تم حفظ نسخة المراجعة — السطور التي أضافها المساعد مطبوعة بالأحمر",
  "Send copy saved — the added lines are printed in black, without the red marks":
    "تم حفظ نسخة الإرسال — السطور المضافة مطبوعة بالأسود، دون العلامات الحمراء",
  "AI Application Assistant": "مساعد التقديمات الذكي",
  "Generate tailored materials from your real profile only — nothing is invented, and nothing is sent for you.":
    "أنشئ مستندات مخصصة من ملفك الشخصي الحقيقي فقط — لا شيء مختلق، ولا شيء يُرسل عنك.",
  "Generate materials": "توليد المستندات",
  "Pick the ad, choose what you need, then generate.":
    "اختر الإعلان، ثم ما تحتاجه، ثم أنشئ.",
  "Jobs unavailable": "الوظائف غير متاحة",
  "No jobs stored yet": "لا توجد وظائف مخزنة بعد",
  "or run a search in": "أو شغّل بحثًا في",
  "Automation Settings": "إعدادات الأتمتة",
  "first.": "أولًا.",
  "What to generate": "ما تريد توليده",
  "Extra notes": "ملاحظات إضافية",
  "optional": "اختياري",
  "e.g. Mention my freelance work, keep it under 200 words, highlight my graduation project…":
    "مثال: اذكر عملي الحر، واجعله أقل من 200 كلمة، وأبرز مشروع التخرج…",
  "Works with or without an AI key — it falls back to a template built from your profile.":
    "يعمل بمفتاح ذكاء اصطناعي أو دونه — ويرجع إلى قالب مبني من ملفك الشخصي.",
  "Generating…": "جارٍ التوليد…",
  "Generate {kind}": "توليد {kind}",
  "Nothing generated yet": "لم يُولَّد شيء بعد",
  'Pick a job and choose "{kind}", then press Generate. Every draft is built from what you entered in your profile.':
    'اختر وظيفة وحدد "{kind}"، ثم اضغط «توليد». كل مسودة مبنية على ما أدخلته في ملفك الشخصي.',
  "Writing your {kind}…": "جارٍ كتابة {kind}…",
  "Template-based": "مبني على قالب",
  "AI generated": "مُولَّد بالذكاء الاصطناعي",
  "{n} additions in red — confirm them": "{n} إضافات بالأحمر — تحقق منها",
  "Editable before you use it": "قابل للتعديل قبل الاستخدام",
  "The copy you check first: additions the assistant suggested for this ad are printed red":
    "النسخة التي تراجعها أولًا: الإضافات التي اقترحها المساعد لهذا الإعلان مطبوعة بالأحمر",
  "The copy for the employer: no red marks, no internal notes, and the added lines stay as normal text":
    "النسخة المخصصة لصاحب العمل: لا علامات حمراء ولا ملاحظات داخلية، وتبقى السطور المضافة نصًا عاديًا",
  "Export .txt": "تصدير .txt",
  "Regenerate": "إعادة التوليد",
  "Edit the text": "تعديل النص",
  "Preview with red marks": "معاينة بالعلامات الحمراء",
  "Generated history": "سجل التوليد",
  "Materials saved for this job": "المستندات المحفوظة لهذه الوظيفة",
  "No saved materials for this job yet.": "لا توجد مستندات محفوظة لهذه الوظيفة بعد.",
  "Loaded from history — review before using.": "حُمّلت من السجل — راجعها قبل الاستخدام.",
  "Template": "قالب",
  "Delete this material": "حذف هذا المستند",
  "Delete this document": "حذف هذا المستند",
  "This saved draft is removed for good. You can always generate it again, but the AI call costs quota.":
    "تُحذف هذه المسودة المحفوظة نهائيًا. يمكنك دائمًا توليدها من جديد، لكن استدعاء الذكاء الاصطناعي يستهلك من الحصة.",

  // automation page
  "Every 24 hours": "كل 24 ساعة",
  "Every {n} days": "كل {n} يوم",
  "Every hour": "كل ساعة",
  "Every {n} hours": "كل {n} ساعة",
  "Every {n} minutes": "كل {n} دقيقة",
  "Remove {term}": "إزالة {term}",
  "Type and press Enter": "اكتب واضغط Enter",
  "This is exactly what an import will ask for": "هذا بالضبط ما سيطلبه الاستيراد",
  "Live preview": "معاينة مباشرة",
  "These titles and skills were copied from your Resume & Profile page because the automation list was empty. Saving them here pins them, and then this editor is the one that decides.":
    "نُسخت هذه المسميات والمهارات من صفحة السيرة والملف الشخصي لأن قائمة الأتمتة كانت فارغة. حفظها هنا يثبّتها، وبعد ذلك يصبح هذا المحرر هو صاحب القرار.",
  "Spelling check — the search uses the corrected term": "تدقيق إملائي — يستخدم البحث المصطلح المصحّح",
  "Your saved text stays exactly as you wrote it; only this search is corrected.":
    "يبقى نصك المحفوظ كما كتبته تمامًا؛ ويجري التصحيح في هذا البحث فقط.",
  "{n} phrases are searched per import ({list}).": "يُبحث عن {n} عبارة في كل استيراد ({list}).",
  "{m} more is not searched yet ({list})": "{m} إضافية لم يُبحث عنها بعد ({list})",
  "{m} more are not searched yet ({list})": "{m} إضافية لم يُبحث عنها بعد ({list})",
  "— free a slot by removing one above.": "— أفرِغ خانة بإزالة واحدة مما سبق.",
  "{n} search": "{n} بحث",
  "{n} searches": "{n} بحث",
  "full listing": "القائمة الكاملة",
  "needs an API key — skipped until then": "يتطلب مفتاح API — يُتخطى حتى توفيره",
  "Automation settings saved": "تم حفظ إعدادات الأتمتة",
  "Tick at least one job site first — otherwise the search would use the saved list, not the boxes you just cleared":
    "حدد موقعًا واحدًا على الأقل أولًا — وإلا فسيستخدم البحث القائمة المحفوظة، لا المربعات التي مسحتها للتو.",
  "Search finished — {n} new jobs": "انتهى البحث — {n} وظيفة جديدة",
  "Search failed: {log}": "فشل البحث: {log}",
  "Setup": "الإعداد",
  "Automation": "الأتمتة",
  "Scheduled searches run in the backend process. Keep the backend running for automation to work.":
    "تعمل عمليات البحث المجدولة داخل عملية الخادم الخلفي. أبقِ الخادم قيد التشغيل لتعمل الأتمتة.",
  "Running…": "جارٍ التشغيل…",
  "Run search now": "تشغيل البحث الآن",
  "Save settings": "حفظ الإعدادات",
  "Search schedule": "جدول البحث",
  "When the app looks for new postings": "متى يبحث التطبيق عن إعلانات جديدة",
  "Active": "نشط",
  "Inactive": "متوقف",
  "Scheduled search": "البحث المجدول",
  "Runs every {n} minutes": "يعمل كل {n} دقيقة",
  "Paused — no automatic runs": "متوقف مؤقتًا — لا تشغيل تلقائي",
  "Search interval": "فترة البحث",
  "Min. match score": "أدنى درجة تطابق",
  "Max job age": "أقصى عمر للإعلان",
  "Newer than {n} days": "أحدث من {n} يوم",
  "Only fetch jobs marked as remote": "جلب الوظائف المحددة كعمل عن بُعد فقط",
  "Search terms": "كلمات البحث",
  "What the scheduled (and manual) search looks for. Each phrase is searched on its own.":
    "ما يبحث عنه البحث المجدول (واليدوي). يجري البحث عن كل عبارة على حدة.",
  "Job titles": "المسميات الوظيفية",
  "Each title is searched on its own, so a posting titled just “Flutter Engineer” still gets caught.":
    "يجري البحث عن كل مسمى على حدة، فيُلتقط حتى الإعلان المكتوب عليه «Flutter Engineer» فقط.",
  "Skills": "المهارات",
  "Experience level": "مستوى الخبرة",
  "Location & remote": "الموقع والعمل عن بُعد",
  "Job title fit": "ملاءمة المسمى الوظيفي",
  "Used after the titles, to fill the remaining search slots.":
    "تُستخدم بعد المسميات، لملء بقية خانات البحث.",
  "Extra fields to hunt in — your choice": "حقول إضافية للبحث فيها — باختيارك",
  "Anything else you want the app to look for, even if it is not in your profile. These rank right after your titles.":
    "أي شيء آخر تريد أن يبحث عنه التطبيق، حتى إن لم يكن في ملفك الشخصي. تأتي هذه في الترتيب مباشرة بعد مسمياتك.",
  "Locations": "المواقع",
  "The first location is the one LinkedIn and Google Jobs search. Currently: {where}.":
    "الموقع الأول هو الذي يبحث فيه LinkedIn وGoogle Jobs. حاليًا: {where}.",
  "Job sources": "مصادر الوظائف",
  "Ticked sites are what the schedule searches. In Find Jobs you can import Egypt jobs or jobs outside Egypt in one press.":
    "المواقع المحددة هي ما يبحث فيه الجدول. وفي صفحة البحث عن وظائف يمكنك استيراد وظائف داخل مصر أو خارجها بضغطة واحدة.",
  "{n} selected": "تم اختيار {n}",
  "no postings yet": "لا إعلانات بعد",
  "To pull one site alone, use its own button in Find Jobs.":
    "جلب موقع واحد فقط: استخدم زرّه الخاص في صفحة البحث عن وظائف.",
  "Searching now": "جارٍ البحث الآن",
  "Live progress from the backend": "تقدّم مباشر من الخادم الخلفي",
  "{label} — site {done} of {total}": "{label} — الموقع {done} من {total}",
  "Starting the search…": "جارٍ بدء البحث…",
  "Run history": "سجل التشغيل",
  "Latest automation runs, newest first": "آخر عمليات الأتمتة، الأحدث أولًا",
  "No runs yet. Press “Run search now” to trigger the first one.":
    "لا توجد عمليات بعد. اضغط «تشغيل البحث الآن» لبدء أول عملية.",
  "{n} new": "{n} جديد",
  "No log output.": "لا مخرجات في السجل.",

  // Profile page
  "Your source of truth": "مصدر بياناتك الأساسي",
  "This profile feeds match scores and everything the AI writes for you. Nothing is ever sent anywhere on its own.":
    "هذا الملف الشخصي هو مصدر درجات التطابق وكل ما يكتبه لك الذكاء الاصطناعي. ولا شيء يُرسل إلى أي مكان من تلقاء نفسه.",
  "Sections": "الأقسام",
  "basic details": "البيانات الأساسية",
  "Profile saved": "تم حفظ الملف الشخصي",
  "Save profile": "حفظ الملف الشخصي",
  "Skill #{n} has no name — fill it in or remove it.":
    "المهارة رقم {n} بلا اسم — اكتب لها اسمًا أو احذفها.",
  'Saved up to "{label}", but that part failed: {error}':
    'تم الحفظ حتى "{label}"، لكن هذا الجزء فشل: {error}',
  " ({n} section(s) not saved)": " ({n} أقسام لم تُحفظ)",
  'Resume "{name}" uploaded': 'تم رفع السيرة "{name}"',
  'Resume "{name}" uploaded and text extracted': 'تم رفع السيرة "{name}" واستخراج النص منها',
  "Resume removed": "تمت إزالة السيرة الذاتية",
  "Nothing readable was found in this CV.": "لم يُعثر على نص قابل للقراءة في هذه السيرة.",
  "Profile updated from your CV ({n} items)": "تم تحديث الملف الشخصي من سيرتك ({n} عناصر)",
  "Profile updated from your CV ({n} item)": "تم تحديث الملف الشخصي من سيرتك ({n} عنصر)",
  "Did you mean": "هل تقصد",
  'instead of “{term}”?': 'بدلًا من “{term}”?',
  "Add {label}": "إضافة {label}",
  "Basic information": "المعلومات الأساسية",
  "Used in generated cover letters and emails — never invent anything beyond this.":
    "تُستخدم في خطابات التقديم والبريد الإلكتروني التي نولّدها — لا نضيف أبدًا شيئًا خارج هذه البيانات.",
  "Email": "البريد الإلكتروني",
  "Phone": "الهاتف",
  "Country": "الدولة",
  "City": "المدينة",
  "LinkedIn": "لينكد إن",
  "GitHub": "GitHub",
  "Portfolio": "معرض الأعمال",
  "Languages": "اللغات",
  "Professional summary": "الملخص المهني",
  "2-3 sentences about who you are and what you do.":
    "جملتان أو ثلاث عنك وعن عملك.",
  "Job preferences": "تفضيلات العمل",
  "These drive your match scores and scheduled searches.":
    "هذه تحدّد درجات التطابق والبحوث المجدولة.",
  "Desired job titles": "المسميات الوظيفية المطلوبة",
  "Preferred locations": "المواقع المفضلة",
  "e.g. Flutter Developer": "مثال: Flutter Developer",
  "e.g. Cairo, Remote": "مثال: القاهرة، عن بُعد",
  "Remote preference": "تفضيل العمل عن بُعد",
  "Open to all (remote / hybrid / onsite)": "متاح للجميع (عن بُعد / هجين / حضوري)",
  "Remote only": "عن بُعد فقط",
  "Hybrid preferred": "أفضّل الهجين",
  "Onsite only": "حضوري فقط",
  "Target levels": "المستويات المستهدفة",
  "Work types": "أنواع العمل",
  "Not part of the match score — filter by employment type in Find Jobs to narrow results.":
    "ليست جزءًا من درجة التطابق — استخدم تصفية نوع التوظيف في صفحة البحث عن وظائف لتضييق النتائج.",
  "Full-time": "دوام كامل",
  "Part-time": "دوام جزئي",
  "Internship": "تدريب",
  "Contract": "عقد",
  "Freelance": "عمل حر",
  "Intern": "متدرب",
  "Entry": "مبتدئ",
  "Entry-level": "مبتدئ",
  "Junior": "مبتدئ",
  "Mid": "متوسط الخبرة",
  "Mid-level": "متوسط الخبرة",
  "Midweight": "متوسط الخبرة",
  "Senior": "خبير",
  "Senior (5-10 years)": "خبير (5–10 سنوات)",
  "Associate": "مساعد",
  "Director": "مدير",
  "Manager": "مدير",
  "Executive": "تنفيذي",
  "Full Time": "دوام كامل",
  "Full time": "دوام كامل",
  "Full-Time": "دوام كامل",
  "full_time": "دوام كامل",
  "full-time": "دوام كامل",
  "fulltime": "دوام كامل",
  "Fulltime": "دوام كامل",
  "Part Time": "دوام جزئي",
  "Part time": "دوام جزئي",
  "Part-Time": "دوام جزئي",
  "part_time": "دوام جزئي",
  "part-time": "دوام جزئي",
  "parttime": "دوام جزئي",
  "Parttime": "دوام جزئي",
  "contract": "عقد",
  "freelance": "عمل حر",
  "internship": "تدريب",
  "Temporary": "مؤقت",
  "Permanent": "دائم",
  "Volunteer": "تطوعي",
  "Apprenticeship": "تدريب مهني",
  "Employee": "موظف",
  "Contractor": "متعاقد",
  "Experienced": "ذو خبرة",
  "Student": "طالب",
  "Trainee": "متدرب",
  "Working student": "طالب يعمل",
  "Full or part time": "دوام كامل أو جزئي",
  "Side job": "عمل جانبي",
  "Team lead": "قائد فريق",
  "Management": "إدارة",
  "Worker": "عامل",
  "Student assistant": "مساعد طالب",
  "Supervisor": "مشرف",
  "Development": "تطوير",
  "Sales": "مبيعات",
  "Administration": "أعمال إدارية",
  "Writing": "كتابة",
  "Design": "تصميم",
  "Marketing": "تسويق",
  "Customer Success": "نجاح العملاء",
  "Profile": "الملف الشخصي",
  "The ad asks for the CV at {email}": "يطلب الإعلان إرسال السيرة الذاتية إلى {email}",
  "The ad links to the company's own application page":
    "يحيل الإعلان إلى صفحة التقديم الخاصة بالشركة نفسها",
  "Apply on {board} — the ad gives no other address":
    "التقديم على {board} — لا يذكر الإعلان طريقة أخرى",
  "Apply on the board page — the ad gives no other address":
    "التقديم من صفحة الإعلان — لا يوجد عنوان آخر مذكور",
  "No way to apply is stated in this ad": "لا توجد طريقة تقديم مذكورة في هذا الإعلان",
  "Entry-Level": "مبتدئ",
  "running": "قيد التشغيل",
  "success": "ناجح",
  "failed": "فاشل",
  "Arabic": "العربية",
  "French": "الفرنسية",
  "German": "الألمانية",
  "Other": "أخرى",
  "Summary": "الملخص",
  "Min. salary": "الحد الأدنى للراتب",
  "Currency": "العملة",
  "Rate each skill 1 (beginner) to 5 (expert). These are matched against every posting.":
    "قيّم كل مهارة من 1 (مبتدئ) إلى 5 (خبير). تُقارن هذه المهارات بكل إعلان.",
  "Add skill": "إضافة مهارة",
  "Skill": "المهارة",
  "Level": "المستوى",
  "Years": "سنوات الخبرة",
  "Skill name": "اسم المهارة",
  "Skill {n} name": "اسم المهارة {n}",
  "Skill {n} level": "مستوى المهارة {n}",
  "Skill {n} years of experience": "سنوات الخبرة في المهارة {n}",
  "Level {n}": "المستوى {n}",
  "skill": "المهارة",
  "No skills yet. Add the ones you can honestly do — they drive the match score.":
    "لا توجد مهارات بعد. أضف المهارات التي تجيدها بصدق — فهي تحدد درجة التطابق.",
  "Work experience": "الخبرة العملية",
  "Add experience": "إضافة خبرة",
  "New role": "دور جديد",
  "Remove experience": "إزالة الخبرة",
  "Job title": "المسمى الوظيفي",
  "Company": "الشركة",
  "Start (YYYY-MM)": "البداية (YYYY-MM)",
  "End (YYYY-MM)": "النهاية (YYYY-MM)",
  "Current role": "أعمل فيه حاليًا",
  "Description": "الوصف",
  "No experience added yet. Add the roles you actually held.":
    "لا توجد خبرات مضافة بعد. أضف الأدوار التي عملت فيها فعلًا.",
  "Education": "التعليم",
  "Add education": "إضافة تعليم",
  "New degree": "شهادة جديدة",
  "Remove education": "إزالة التعليم",
  "Degree": "الشهادة",
  "Institution": "الجهة",
  "Field": "التخصص",
  "Start": "البداية",
  "End": "النهاية",
  "No education added yet.": "لا يوجد تعليم مضاف بعد.",
  "Projects": "المشاريع",
  "Projects & portfolio": "المشاريع والأعمال",
  "Add project": "إضافة مشروع",
  "New project": "مشروع جديد",
  "Remove project": "إزالة المشروع",
  "Project name": "اسم المشروع",
  "URL": "الرابط",
  "Technologies (comma separated)": "التقنيات (مفصولة بفاصلة)",
  "No projects added yet. Real projects you built are worth showing.":
    "لا توجد مشاريع مضافة بعد. المشاريع الحقيقية التي بنيتها جديرة بالعرض.",
  "Resume file": "ملف السيرة الذاتية",
  "PDF, TXT, DOCX or MD up to 5 MB. Text is extracted from all of them so the AI can use it. Old .doc files: save as .docx or PDF first. Files are never executed.":
    "PDF أو TXT أو DOCX أو MD بحجم أقصى 5 ميجابايت. يُستخرج النص من جميعها ليستخدمه الذكاء الاصطناعي. ملفات .doc القديمة: احفظها بصيغة .docx أو PDF أولًا. لا تُنفَّذ الملفات مطلقًا.",
  "Text extracted — the AI can read it": "تم استخراج النص — يمكن للذكاء الاصطناعي قراءته",
  "No readable text — match scores can't use it": "لا يوجد نص مقروء — لا يمكن لدرجات التطابق استخدامه",
  "Fill your profile from this resume": "تعبئة ملفك الشخصي من هذه السيرة",
  "No readable text in this file": "لا يوجد نص مقروء في هذا الملف",
  "Auto-fill from CV": "تعبئة تلقائية من السيرة",
  "Uploading…": "جارٍ الرفع…",
  "Upload your resume": "رفع سيرتك الذاتية",
  "PDF / TXT / DOCX / MD, max 5 MB": "PDF / TXT / DOCX / MD، بحد أقصى 5 ميجابايت",
  "Auto-fill from your CV": "تعبئة تلقائية من سيرتك الذاتية",
  "Read literally from your uploaded resume. Nothing is saved until you press Apply.":
    "نقرأ حرفيًا من سيرتك المرفوعة. لا شيء يُحفظ حتى تضغط «تطبيق».",
  "Contact & summary": "التواصل والملخص",
  "replaces current": "سيستبدل الحالي",
  "Now: {current}": "حاليًا: {current}",
  "Already on your profile": "موجود بالفعل في ملفك الشخصي",
  "already on your profile": "موجود بالفعل في ملفك الشخصي",
  "Present": "حتى الآن",
  "{n} of {total} found items selected": "اخترت {n} من {total} عنصرًا موجودًا",
  "Apply selected": "تطبيق المحدد",
  "Remove your resume file": "إزالة ملف السيرة",
  "The uploaded file and the text read from it are deleted. Your saved profile details stay — only the resume goes. You would have to upload the file again.":
    "يُحذف الملف المرفوع والنص المستخرج منه. تبقى تفاصيل ملفك المحفوظة — تُحذف السيرة وحدها. وسيلزمك رفع الملف مرة أخرى.",
  "Remove resume": "إزالة السيرة",
  "Close": "إغلاق",

  // dashboard page
  "Good morning": "صباح الخير",
  "Good afternoon": "مساء الخير",
  "Good evening": "مساء الخير",
  "Here is your job hunt today — every number comes from your own data.":
    "هذا وضع بحثك عن العمل اليوم — كل رقم مستمد من بياناتك أنت.",
  "AI matches": "التطابقات بالذكاء الاصطناعي",
  "Your profile needs a little more detail": "ملفك الشخصي يحتاج إلى مزيد من التفاصيل",
  "Match scores get sharper when your skills and experience are filled in.":
    "تتحسن درجات التطابق عند إكمال مهاراتك وخبراتك.",
  "Complete profile": "إكمال الملف الشخصي",
  "Jobs discovered": "وظائف مكتشفة",
  "Matches 70+": "تطابقات 70+",
  "Saved jobs": "وظائف محفوظة",
  "Applications": "التقديمات",
  "Interviews": "مقابلات",
  "Offers": "عروض عمل",
  "{count} posting(s) are hidden from the lists because their source no longer advertises them — the numbers above count live openings only.":
    "يُخفى {count} إعلان من القوائم لأن مصدره لم يعد يعرضه — والأرقام أعلاه تحتسب الوظائف المتاحة فقط.",
  "Best matching jobs": "أفضل الوظائف المطابقة",
  "Highest estimated scores for your profile": "أعلى الدرجات التقديرية لملفك الشخصي",
  "View all": "عرض الكل",
  "Complete your profile to see your best matches.":
    "أكمل ملفك الشخصي لرؤية أفضل التطابقات.",
  "Application status": "حالة التقديمات",
  "Where your tracked applications stand": "أين تقف تقديماتك التي تتابعها",
  "No applications tracked yet.": "لا توجد تقديمات متابعة بعد.",
  "Recent discoveries": "أحدث الاكتشافات",
  "Latest jobs added to your database": "أحدث الوظائف المضافة إلى قاعدة بياناتك",
  "Browse": "تصفّح",
  "No jobs imported yet — start with Find Jobs.":
    "لا توجد وظائف مستوردة بعد — ابدأ من صفحة البحث عن وظائف.",
  "Follow-ups due": "المتابعات المستحقة",
  "Soonest first — overdue ones are marked": "الأقرب أولًا — تُعلَّم المتأخرة",
  "No follow-ups scheduled yet. Set a follow-up date on an application in the tracker.":
    "لا توجد متابعات مجدولة بعد. حدد تاريخ متابعة لتقديم في أداة المتابعة.",
  "Overdue": "متأخرة",
};

export type Lang = "en" | "ar";

/**
 * The language the app answers in, kept in a module variable instead of being read
 * off `<html lang>`.
 *
 * The provider writes that attribute in an effect, which runs after the render it
 * came from — so anything formatting text during the switch would still see the old
 * language and the card's posting time would stay English in Arabic mode.
 */
let current: Lang = storedLang();

export function storedLang(): Lang {
  const saved = localStorage.getItem("jobhunter-lang");
  if (saved === "ar" || saved === "en") return saved;
  return navigator.language.toLowerCase().startsWith("ar") ? "ar" : "en";
}

export function setTranslateLang(lang: Lang): void {
  current = lang;
}

/** The active language for code that cannot use the React context. */
export function translateLang(): Lang {
  return current;
}

/** Translation usable outside React (e.g. error boundaries). */
export function translate(key: string, vars?: Record<string, string | number>): string {
  let text = current === "ar" ? (AR[key] ?? key) : key;
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.split(`{${name}}`).join(String(value));
    }
  }
  return text;
}
