"""Real-format fixture jobs for the test suite (no demo data)."""

CORE = [
    dict(title="Junior Flutter Developer", company="NileSoft", location="Cairo", remote=False,
         level="Junior", skills=["Flutter", "Dart", "REST APIs"]),
    dict(title="Flutter Developer", company="Cairo Tech", location="Cairo", remote=False,
         level="Junior", skills=["Flutter", "Dart", "Firebase"]),
    dict(title="Senior Flutter Developer", company="GlobeTech", location="Remote", remote=True,
         level="Senior", skills=["Flutter", "Dart", "BLoC"]),
    dict(title="Web Development Intern", company="Cairo Dev Academy", location="Cairo", remote=False,
         level="Intern", skills=["HTML", "CSS", "JavaScript"]),
    dict(title="Python/Django Developer", company="EventSphere", location="Giza", remote=False,
         level="Mid", skills=["Python", "Django", "PostgreSQL"]),
    dict(title="C# .NET Developer", company="EnterpriseEG", location="Cairo", remote=False,
         level="Mid", skills=["C#", ".NET", "SQL Server"]),
    dict(title="Flutter Developer (Remote)", company="RemoteApps", location="Remote", remote=True,
         level="Junior", skills=["Flutter", "Dart"]),
    dict(title="Frontend Developer React", company="WebWorks", location="Alexandria", remote=False,
         level="Junior", skills=["React", "JavaScript", "CSS"]),
    dict(title="Python Developer", company="DataNile", location="Cairo", remote=False,
         level="Junior", skills=["Python", "Pandas", "SQL"]),
    dict(title="Flutter Intern", company="StartUpX", location="Cairo", remote=False,
         level="Intern", skills=["Flutter", "Dart"]),
    dict(title="Remote Flutter Developer", company="Upwork Client", location="Remote", remote=True,
         level="Junior", skills=["Flutter", "Firebase"]),
    dict(title="Mobile Developer", company="AppMakers", location="Cairo", remote=False,
         level="Mid", skills=["Flutter", "Kotlin"]),
    dict(title="Junior Software Developer", company="SoftLand", location="Cairo", remote=False,
         level="Junior", skills=["Python", "Java"]),
    dict(title="Flutter Developer (IoT)", company="SmartHome EG", location="Cairo", remote=False,
         level="Junior", skills=["Flutter", "Dart", "MQTT"]),
]

FIXTURE_JOBS = CORE + [
    dict(title=f"Backend Developer {i}", company=f"BackendCo {i}", location="Cairo", remote=False,
         level="Mid", skills=["Python", "FastAPI"])
    for i in range(1, 11)
]
