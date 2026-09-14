# Dokumentacja techniczna (PL)

Pełny, techniczny opis działania projektu **Power Platform Documentation
Manager**: co robi każdy skrypt/moduł, z czego korzysta i jak elementy
łączą się w całość. Ten dokument jest polskojęzycznym odpowiednikiem
`ARCHITECTURE.md` + `DECISIONS.md`, rozszerzonym o konkretne ustalenia z
realnej weryfikacji przeciwko prawdziwej (testowej) dzierżawie Power
Platform — nie jest tłumaczeniem 1:1, tylko praktycznym przewodnikiem „jak
to naprawdę działa”.

## Spis treści

1. [Co to za system i po co powstał](#1-co-to-za-system-i-po-co-powstał)
2. [Ograniczenia projektowe — czego celowo tu nie ma](#2-ograniczenia-projektowe--czego-celowo-tu-nie-ma)
3. [Architektura na wysokim poziomie](#3-architektura-na-wysokim-poziomie)
4. [Struktura repozytorium](#4-struktura-repozytorium)
5. [SharePoint jako źródło prawdy](#5-sharepoint-jako-źródło-prawdy)
6. [Aplikacja Power Apps](#6-aplikacja-power-apps)
7. [Worker — jak przetwarza zadania](#7-worker--jak-przetwarza-zadania)
8. [Adaptery — jak system rozmawia ze światem zewnętrznym](#8-adaptery--jak-system-rozmawia-ze-światem-zewnętrznym)
9. [Normalizacja, porównywanie wersji i ocena wpływu](#9-normalizacja-porównywanie-wersji-i-ocena-wpływu)
10. [Wersjonowanie dokumentacji](#10-wersjonowanie-dokumentacji)
11. [Generowanie dokumentacji](#11-generowanie-dokumentacji)
12. [Integracja z Copilot](#12-integracja-z-copilot)
13. [Skrypty pomocnicze](#13-skrypty-pomocnicze)
14. [Konfiguracja](#14-konfiguracja)
15. [Bezpieczeństwo](#15-bezpieczeństwo)
16. [Testowanie](#16-testowanie)
17. [Realnie napotkane i rozwiązane błędy](#17-realnie-napotkane-i-rozwiązane-błędy)
18. [Znane ograniczenia i rzeczy niedokończone](#18-znane-ograniczenia-i-rzeczy-niedokończone)

---

## 1. Co to za system i po co powstał

To wewnętrzne narzędzie, które **automatycznie dokumentuje i wersjonuje**
aplikacje/rozwiązania Microsoft Power Platform. Ktoś rejestruje aplikację
przez prosty formularz w Power Apps, klika „Żądaj dokumentacji”, a system
sam:

1. eksportuje rozwiązanie Power Platform (przez `pac` CLI),
2. sprowadza je do ujednoliconej, przewidywalnej reprezentacji JSON,
3. porównuje ją z poprzednią wersją (jeśli istnieje) i wykrywa dokładnie,
   co się zmieniło,
4. ocenia, jak istotna jest ta zmiana — osobno z perspektywy technicznej i
   osobno z perspektywy użytkownika końcowego,
5. generuje dwa dokumenty Markdown (dokumentację techniczną i przewodnik
   użytkownika) oraz krótkie podsumowanie zmian,
6. zapisuje wszystko z powrotem do SharePoint i aktualizuje numer wersji.

Całość działa w pełni **offline i bez żadnych kosztów licencyjnych ponad
standardowy Microsoft 365/Power Platform** — nie wymaga Dataverse, nie
wymaga konektorów Premium, nie wymaga Azure. Może też działać z Copilotem
(opcjonalnie) albo bez niego — z ręcznym udziałem człowieka w generowaniu
treści, albo w pełni deterministycznie, na podstawie szablonów.

## 2. Ograniczenia projektowe — czego celowo tu nie ma

To są świadome, opisane w `CLAUDE.md` decyzje, nie przeoczenia:

- **Brak Dataverse.** Cała trwałość danych jest w standardowych listach
  SharePoint Online — Dataverse wymaga licencji Premium.
- **Brak konektorów Premium/niestandardowych ani konektora HTTP w Power
  Automate.** Cała logika biznesowa jest w osobnym procesie Python
  (workerze), a nie w samych flow.
- **Brak usług Azure** (Key Vault, Functions, Logic Apps) jako wymogu —
  są dopuszczalne wyłącznie jako świadomie zaakceptowane rozszerzenie,
  nigdy jako wymóg dla podstawowej funkcjonalności.
- **Zero zależności sieciowych dla ścieżki mockowej.** Cały pakiet
  worker/ działa i jest testowany bez dostępu do internetu, dzięki
  mockowym implementacjom każdego adaptera zewnętrznego.

## 3. Architektura na wysokim poziomie

```
Power Apps (formularz)
      │  zapis/odczyt list
      ▼
SharePoint Online  ◄──────────────┐   (jedyne źródło prawdy o stanie zadań)
   │  Applications                │
   │  DocumentationJobs           │
   │  DocumentationVersions       │
   │  Configuration (opc.)        │
   │  biblioteka dokumentów       │
      │  odpytywanie (poll)       │
      ▼                           │
   Worker (Python, proces ciągły albo --once)
      │
      ├─ PowerPlatformAdapter  → `pac` CLI → eksport/rozpakowanie rozwiązania
      ├─ normalizacja          → deterministyczny JSON
      ├─ silnik różnic (diff)  → co się zmieniło, pole po polu
      ├─ analiza wpływu        → NONE/LOW/MEDIUM/HIGH (technicznie i dla użytkownika)
      ├─ CopilotAdapter        → generowanie treści (mock / człowiek / Copilot Studio)
      ├─ generator dokumentacji → trzy pliki Markdown
      └─ SharePointAdapter     → zapis wyników z powrotem ────────────────┘

Power Automate (opcjonalnie)
      │  wyłącznie powiadomienia (e-mail) — NIGDY kolejka zadań
      ▼
   Office 365 Outlook
```

**Kluczowa zasada architektoniczna**: Power Apps i Power Automate **nigdy**
nie wywołują workera bezpośrednio ani nie uruchamiają PowerShella — jedyny
sposób komunikacji to zapis/odczyt wierszy w listach SharePoint. Dzięki
temu worker można całkowicie wymienić, przenieść, uruchamiać lokalnie albo
w chmurze — z punktu widzenia Power Apps nic się nie zmienia.

**Każdy system zewnętrzny jest schowany za interfejsem adaptera** —
`PowerPlatformAdapter`, `CopilotAdapter`, `SharePointAdapter` — z co
najmniej jedną mockową implementacją każdego. Logika biznesowa w `worker/`
nigdy nie importuje bezpośrednio żadnego SDK dostawcy ani nie wywołuje
`pac`/PowerShell — robi to wyłącznie moduł `real.py` wewnątrz danego
pakietu adaptera. Dzięki temu przełączenie mock → prawdziwa integracja to
wyłącznie zmiana konfiguracji (`worker/config.py`), nigdy zmiana kodu w
`job_processor.py` ani w logice normalizacji/diff/wersjonowania.

## 4. Struktura repozytorium

```
CLAUDE.md            wytyczne robocze dla pracy nad repo (dla ludzi i AI)
ARCHITECTURE.md       architektura systemu (EN)
DECISIONS.md          rejestr decyzji architektonicznych, ADR-001…ADR-008 (EN)
ROADMAP.md             status kamieni milowych (EN)
SECURITY.md            model bezpieczeństwa (EN)
README.md               opis projektu (EN)

docs/                  dokumenty pogłębione, w tym te dwa polskojęzyczne
worker/                jedyny wykonywalny kod backendu (Python)
examples/mock_solution/ dane przykładowe dla adaptera mockowego (wersje v1.0/v1.1)
scripts/                 skrypty setup/run/demo/test (bash + PowerShell)
config/                  szablony konfiguracji bez sekretów (.env.example)
sharepoint/               schematy list + skrypt provisioningu
powerapps/                 specyfikacja ekranów/formuł + wygenerowana aplikacja .msapp
powerautomate/              specyfikacja opcjonalnych flow
```

Wewnętrzna struktura `worker/`:

```
worker/main.py                    punkt wejścia — pętla odpytywania
worker/config.py                  konfiguracja z env, zero sekretów w kodzie
worker/models.py                  enumy + dataclassy współdzielone w całym workerze
worker/job_processor.py           orkiestracja cyklu życia jednego zadania
worker/queue/job_queue.py          cienka nakładka na kolejkę zadań (przez SharePointAdapter)
worker/adapters/
    powerplatform/  base.py, mock.py, real.py, pac_cli.py, xml_parsing.py
    copilot/        base.py, mock.py, human_review.py, real.py, direct_line.py, exceptions.py
    sharepoint/     base.py, mock.py, real.py, graph_client.py
    factory.py       JEDYNE miejsce, które importuje konkretne (nie-bazowe) implementacje adapterów
worker/normalization/  schema.py, normalizer.py
worker/diff/            engine.py, impact.py
worker/versioning/version.py
worker/documentation/generator.py
worker/logging_setup.py
worker/tests/            zestaw testów pytest
```

## 5. SharePoint jako źródło prawdy

Cztery listy + jedna biblioteka dokumentów, opisane dokładnie (kolumna po
kolumnie) w `sharepoint/lists/*.json` — to jest jedyne źródło prawdy dla
nazw i typów kolumn, którego muszą trzymać się zarówno skrypt
provisioningu, jak i `RealSharePointAdapter`.

### `Applications` — zarejestrowane aplikacje/rozwiązania

Jeden wiersz na każdą zarejestrowaną aplikację: `Title`, `ApplicationId`,
`SolutionName`, `Environment` (Wybór: DEV/TEST/UAT/PROD), `EnvironmentUrl`
(zwykły tekst — patrz sekcja 17 dlaczego nie „Hiperłącze”), `Owner`
(Osoba), `BusinessOwner` (Osoba), `Description`, `CurrentVersion`
(zapisywane przez workera), `DocumentationStatus` (Wybór:
NOT_DOCUMENTED/DOCUMENTED/UPDATE_AVAILABLE/DOCUMENTATION_FAILED),
`LastDocumented`, `LastAnalyzed`, `TechnicalDocumentationUrl`,
`UserDocumentationUrl`, `Active` (Tak/Nie).

### `DocumentationJobs` — kolejka zadań

To jest **jedyna** kolejka zadań w całym systemie — żadna inna struktura
danych nie pełni tej roli. Kolumny: `Title`, `Application` (Lookup do
`Applications.Title`), `Action` (Wybór: REGISTER_APPLICATION /
DOCUMENT_APPLICATION / EXPORT_SOLUTION / ANALYZE_SOLUTION /
COMPARE_VERSION / GENERATE_DOCUMENTATION / PUBLISH_DOCUMENTATION /
UPDATE_DOCUMENTATION), `RequestedBy` (Osoba), `RequestedAt`, `Status`
(Wybór: PENDING/RUNNING/COMPLETED/FAILED/NEEDS_HUMAN_REVIEW/CANCELLED),
`InputVersion`, `OutputVersion` (zapisywane przez workera), `WorkerId`
(ustawiane przy przejęciu zadania), `StartedAt`, `CompletedAt`,
`ErrorMessage`, `ResultSummary`, `CopilotStatus` (Wybór:
NOT_REQUESTED/MOCKED/PENDING_HUMAN_REVIEW/COMPLETED/FAILED),
`RetryCount`.

### `DocumentationVersions` — historia wygenerowanej dokumentacji

Jeden wiersz na każdą wygenerowaną wersję dokumentacji dla danej
aplikacji: `Title`, `Application` (Lookup), `Version`, `PreviousVersion`,
`ChangeSummary` (tekst wielowierszowy, Markdown), `DocumentationImpact`
(tekst, np. `"technical=HIGH user=HIGH"`), `SnapshotPath`, `DiffPath`,
`TechnicalDocumentationPath`, `UserDocumentationPath`, `CreatedBy`.

### `Configuration` (opcjonalna)

Prosta lista klucz-wartość (`Title`, `Value`, `Description`) na
ewentualne parametry konfiguracyjne. **Nigdy** nie wolno w niej trzymać
poświadczeń ani identyfikatorów dzierżawy.

### Biblioteka dokumentów `PowerPlatformDocumentation`

Struktura: `PowerPlatformDocumentation/<NazwaAplikacji>/<wersja>/` z
plikami `snapshot.json` (znormalizowana reprezentacja), `solution-info.json`
(surowe metadane rozwiązania), `diff.json` (strukturalna różnica względem
poprzedniej wersji), `technical-documentation.md`,
`user-guide.md`. Foldery `_jobs`, `_templates`, `_logs` są tworzone z góry
— `_jobs/<id-zadania>/` przechowuje artefakty specyficzne dla zadania
(np. prompt dla Copilota przy trybie `human_review`).

### Dlaczego nazwy kolumn są bez spacji

SharePoint czasem tworzy inną **wewnętrzną** nazwę kolumny (używaną przez
API) niż nazwę wyświetlaną, jeśli ta ostatnia zawiera spację (np.
„Application Id” → wewnętrznie `Application_x0020_Id`). Żeby tego uniknąć,
wszystkie nazwy kolumn w tym projekcie są jednowyrazowe/PascalCase.

## 6. Aplikacja Power Apps

### Zamierzone 9 ekranów (specyfikacja w `powerapps/README.md`)

1. **Dashboard/Pulpit** — liczniki (zadania oczekujące, aplikacje
   wymagające aktualizacji), galeria ostatnich zadań.
2. **Applications/Lista aplikacji** — wyszukiwarka + galeria zarejestrowanych
   aplikacji.
3. **Application Details/Szczegóły aplikacji** — akcje: żądanie
   dokumentacji/aktualizacji, analiza bieżącej wersji, otwarcie
   dokumentacji, historia wersji.
4. **Register Application/Rejestracja aplikacji** — formularz tworzący
   wiersz w `Applications`.
5. **Request Documentation/Żądanie dokumentacji** — tworzy zadanie
   `DOCUMENT_APPLICATION`.
6. **Request Update/Żądanie aktualizacji** — tworzy zadanie
   `UPDATE_DOCUMENTATION`.
7. **Version History/Historia wersji** — galeria wpisów z
   `DocumentationVersions`.
8. **Job History/Historia zadań** — galeria wpisów z `DocumentationJobs`,
   z przyciskiem ponowienia nieudanego zadania.
9. **Admin/Diagnostics** — widok pomocniczy (lista `Configuration`,
   liczniki zadań wg statusu).

### Faktycznie wygenerowana i zweryfikowana aplikacja

Poza samą specyfikacją, w tym repozytorium (`powerapps/generated/`) istnieje
**gotowy, w pełni działający plik `.msapp`** — nie tylko projekt na
papierze. Został zbudowany jako kod źródłowy (`.pa.yaml`), spakowany
narzędziem `pac canvas pack`, zaimportowany do prawdziwej (testowej)
dzierżawy i iteracyjnie naprawiany aż wszystkie 9 ekranów działało bez
błędów na żywych danych z SharePoint.

**Rzeczywiste nazwy ekranów różnią się nieznacznie od specyfikacji** —
`Screen1` (Pulpit — pozostawiony pod domyślną nazwą Studio), `Applications`
→ **`ApplicationsScreen`** (zmienione celowo, patrz niżej dlaczego),
`ApplicationDetails`, `RegisterApplication`, `RequestDocumentation`,
`RequestUpdate`, `VersionHistory`, `JobHistory`, `AdminDiagnostics`.

Zastosowane, sprawdzone identyfikatory kontrolek: `GroupContainer@1.5.0`
(wariant `AutoLayout`), `Label@2.5.1`, `Classic/Button@2.2.0`,
`Classic/TextInput@2.3.2`, `Gallery@2.15.0` (wariant
`BrowseLayout_Vertical_TwoTextOneImageVariant_ver5.0`).

### Konkretne kształty zapisu `Patch()` do SharePoint

To są **realnie odkryte, nieoczywiste** wymagania konektora SharePoint w
Power Apps — nie są udokumentowane wprost przez Microsoft w jednym
miejscu, znaleziono je metodą prób i błędów, czytając dokładne komunikaty
edytora formuł w Studio:

**Kolumna typu Wybór (Choice)** — sam tekst nie wystarczy, trzeba podać
pełny obiekt z trzema polami:
```
{Value: "PENDING", Id: 0, '@odata.type': "#Microsoft.Azure.Connectors.SharePoint.SPListExpandedChoice"}
```

**Kolumna typu Lookup** (np. `Application` w `DocumentationJobs`) — nie
wolno przypisać całego powiązanego rekordu, tylko dokładnie te dwa pola:
```
{Id: SelectedApplication.ID, Value: SelectedApplication.Title}
```

**Kolumna typu Osoba/Grupa**:
```
{
    '@odata.type': "#Microsoft.Azure.Connectors.SharePoint.SPListExpandedUser",
    Claims: "i:0#.f|membership|" & Lower(User().Email),
    Department: "", DisplayName: User().FullName,
    Email: User().Email, JobTitle: "", Picture: ""
}
```

**Odczyt** kolumn typu Choice/Lookup wymaga jawnego `.Value` (np.
`ThisItem.Status.Value`), a nie samej nazwy właściwości — bez `.Value`
porównania w stylu `Status = "FAILED"` po prostu nigdy nie są prawdziwe.

### Pułapka: nazwa ekranu identyczna z nazwą źródła danych

To jedno z ważniejszych odkryć przy budowie tej aplikacji. Jeśli ekran
nazywa się tak samo jak źródło danych (np. ekran „Applications” i lista
danych „Applications”), Studio **po cichu** zmienia nazwę ekranu (np. na
„Applications_1”) i przepisuje **wszystkie** formuły odwołujące się do tej
nazwy tak, by wskazywały na przemianowany ekran, a nie na listę danych —
nawet po ręcznym poprawieniu formuły i jawnym zacytowaniu nazwy w cudzysłowie
(`'Applications'`), formuła i tak rozwiązywała się z powrotem do ekranu.
Jedynym skutecznym rozwiązaniem było **zmienienie nazwy samego ekranu**
(na `ApplicationsScreen`) wszędzie w kodzie źródłowym, łącznie z każdym
wywołaniem `Navigate(Applications, ...)`.

### Pułapka: niepodłączone źródło danych wygląda jak błąd typu

Jeśli formuła odwołuje się do listy SharePoint, która nigdy nie została
faktycznie dodana jako źródło danych w Studio (**Widok → Dane**), każde
wyrażenie z niej wyprowadzone jest oznaczane jako błąd typu „Error” —
dokładnie tak samo, jak wyglądałby prawdziwy błąd niezgodności typów.
To realnie spowodowało długie dochodzenie przyczyny błędu na ekranie
Historia wersji (`VersionHistory`) — sama formuła była poprawna od
początku, problemem było wyłącznie brakujące podłączenie listy
`DocumentationVersions` jako źródła danych.

## 7. Worker — jak przetwarza zadania

`worker/main.py` uruchamia pętlę (albo pojedynczy przebieg z flagą
`--once`), która woła `JobProcessor.process_next()`.

### Cykl życia jednego zadania

```
PENDING ──(claim_job, atomowa zmiana statusu)──► RUNNING
   │                                                 │
   │                                          sukces │
   │                                                 ▼
   │                                            COMPLETED
   │
   │  błąd, budżet ponowień jeszcze niewyczerpany
   ├──────────────────────────────────────────► z powrotem PENDING (RetryCount += 1)
   │
   │  błąd, budżet ponowień wyczerpany
   └──────────────────────────────────────────► FAILED

   Copilot niedostępny / wymaga człowieka ──────► NEEDS_HUMAN_REVIEW
                                                     │ administrator dostarcza wynik
                                                     ▼
                                                  RUNNING → COMPLETED
```

`JobProcessor._handler_for(action)` mapuje typ akcji na konkretną metodę:
`REGISTER_APPLICATION` (tylko potwierdza istnienie wpisu w
`Applications`), `DOCUMENT_APPLICATION`/`UPDATE_DOCUMENTATION`/
`GENERATE_DOCUMENTATION` (wszystkie trzy prowadzą do tej samej pełnej
ścieżki: eksport → normalizacja → diff → wpływ → generowanie
dokumentacji → zapis), `EXPORT_SOLUTION` (tylko eksport i zapis surowych
metadanych, bez generowania dokumentacji), `ANALYZE_SOLUTION` (liczy
zmiany i aktualizuje `DocumentationStatus` na `UPDATE_AVAILABLE`, jeśli
coś się zmieniło, ale nie generuje dokumentów), `COMPARE_VERSION` (zapisuje
sam `diff.json` jako artefakt zadania), `PUBLISH_DOCUMENTATION` (oznacza
najnowszą wersję jako opublikowaną).

### Idempotentność — bezpieczne ponowienia

Jeśli worker padnie w trakcie przetwarzania (np. między zapisaniem
artefaktów a zaktualizowaniem statusu zadania), kolejne podjęcie tego
samego zadania **nie wygeneruje duplikatu** wersji dokumentacji. Przed
wygenerowaniem nowej wersji `_handle_full_pipeline()` sprawdza, czy wersja
docelowa (`to_version`) już istnieje w `DocumentationVersions` — jeśli
tak, uznaje pracę za już wykonaną i tylko aktualizuje status zadania na
`COMPLETED`, bez powtarzania kosztownej pracy.

### Ważna, realnie odkryta różnica: `environment` vs `environment_url`

`Application.environment` to przyjazna etykieta („DEV”, „PROD”), a
`Application.environment_url` to faktyczny adres URL środowiska, którego
potrzebuje `pac` CLI jako parametr `--environment`. Adapter mockowy
ignorował tę różnicę całkowicie (nie potrzebował URL-a), więc błąd (worker
przekazywał etykietę zamiast URL-a) ujawnił się dopiero przy realnym
uruchomieniu przeciwko prawdziwemu środowisku — to dobry przykład, dlaczego
przechodzenie testów na mockach nie dowodzi, że integracja z prawdziwym
systemem zadziała (zasada wyraźnie zapisana w `CLAUDE.md`).

## 8. Adaptery — jak system rozmawia ze światem zewnętrznym

`worker/adapters/factory.py` to **jedyne** miejsce w całym projekcie,
które importuje konkretne (nie-bazowe) klasy adapterów — cała reszta kodu
zależy wyłącznie od abstrakcyjnych klas bazowych (`abc.ABC`). Wybór trybu
(mock/real/human_review) to wyłącznie decyzja konfiguracyjna
(`worker/config.py`), nigdy zmiana kodu.

### `PowerPlatformAdapter`

Interfejs: `authenticate()`, `list_solutions()`, `export_solution()`,
`unpack_solution()`, `get_solution_metadata()`, `get_application_metadata()`.

- **`MockPowerPlatformAdapter`** czyta pliki z
  `examples/mock_solution/<NazwaRozwiązania>/<wersja>/` (np.
  `solution.json`, `apps.json`, `flows.json` itd.) — brakujący plik po
  prostu daje pustą listę/słownik zamiast błędu.
- **`RealPowerPlatformAdapter`** faktycznie woła `pac` CLI przez
  `pac_cli.py` (cienką nakładkę na `subprocess`) i parsuje wynik przez
  `xml_parsing.py`. Metadane rozwiązania (`Other/Solution.xml`, XML — nie
  JSON jak w mocku), konektory (`Other/Customizations.xml`), zmienne
  środowiskowe (`environmentvariabledefinitions/<schemat>/`), definicje
  flow (`Workflows/<nazwa>-<guid>.json`, format przypominający Logic
  Apps: kroki jako słownik kluczowany nazwą kroku, kolejność wykonania
  wynika z grafu `runAfter`, nie z kolejności w tablicy) — wszystko to
  zostało **realnie zweryfikowane** na prawdziwej dzierżawie testowej.
  Aplikacje canvas (ekrany, kontrolki) — zweryfikowane wobec dwóch
  prawdziwych aplikacji, obie w starszym, przestarzałym formacie
  `Experimental` (nowszy format `SourceCode` wymaga
  `MSAppStructureVersion ≥ 2.4.0`, którego żadna z dostępnych aplikacji
  testowych nie miała). Tabele, role bezpieczeństwa i ogólne komponenty
  pozostają na razie niezweryfikowane (kod zwraca dla nich puste listy).

### `SharePointAdapter`

Interfejs obejmuje operacje na zadaniach (`create_job`, `get_job`,
`get_pending_jobs`, `claim_job`, `update_job`), na aplikacjach
(`get_application`, `list_applications`, `upsert_application`), na
wersjach dokumentacji (`get_latest_version_record`, `list_versions`,
`create_version_record`, `get_snapshot`) oraz na artefaktach
(`upload_document`, `upload_job_artifact`, `read_job_artifact`).

- **`MockSharePointAdapter`** trzyma wszystko w plikach JSON pod lokalnym
  katalogiem (`.local_data/` domyślnie) — biblioteka dokumentów jest
  zwykłą strukturą folderów na dysku.
- **`RealSharePointAdapter`** korzysta z **Microsoft Graph**
  (`GraphClient` w `graph_client.py`), uwierzytelniając się jako aplikacja
  (client credentials flow przez `msal.ConfidentialClientApplication`, bez
  zalogowanego użytkownika). Kluczowe mechanizmy:
  - **Przejęcie zadania (`claim_job`)** korzysta z optymistycznej
    współbieżności SharePoint: odczytuje `@odata.etag` wiersza i wysyła
    warunkowy `PATCH` z nagłówkiem `If-Match`. Jeśli inny worker już
    przejął zadanie w międzyczasie, etag się nie zgadza, żądanie odrzuca
    się jako konflikt, a `claim_job()` interpretuje to jako „już zajęte”
    (zwraca `False`) zamiast rzucać wyjątek.
  - **Zapis kolumn Osoba/Grupa**: `find_user_lookup_id()` odpytuje ukrytą
    listę „Informacje o użytkowniku” (User Information List) po adresie
    e-mail, żeby znaleźć wewnętrzny identyfikator użytkownika SharePoint,
    a następnie zapisuje pole `{NazwaKolumny}LookupId`. Jeśli dana osoba
    nigdy nie odwiedziła tej konkretnej witryny, nie istnieje jeszcze w tej
    liście — resolution zwraca `None`, a pole jest po cichu pomijane
    zamiast przerywać cały zapis (to oczekiwany, nie błędny scenariusz).
    Uwaga: **odczyt z powrotem nie działa** — kolumny `Owner`,
    `BusinessOwner`, `RequestedBy`, `CreatedBy` po odczycie pokazują się
    jako puste teksty nawet gdy mają ustawioną wartość; nic w potoku
    przetwarzania nie polega na odczytywaniu ich z powrotem, więc to luka
    czysto kosmetyczna, nie funkcjonalna.

### `CopilotAdapter`

Interfejs: `analyze_changes()`, `generate_technical_documentation()`,
`generate_user_documentation()`, `generate_change_summary()`.

- **`MockCopilotAdapter`** — deterministyczne generowanie treści przez
  szablony w `worker/documentation/generator.py`, bez żadnego wywołania
  sieciowego.
- **`HumanReviewCopilotAdapter`** — buduje samowystarczalny prompt
  (tytuł/środowisko aplikacji, znormalizowany JSON, diff, ocena wpływu),
  zapisuje go do `_jobs/<id-zadania>/copilot-prompt.md`, ustawia zadanie na
  `NEEDS_HUMAN_REVIEW` i czeka na ręczne dostarczenie wyniku.
- **`RealCopilotAdapter`** — łączy się z agentem **Copilot Studio** przez
  **Direct Line API** (`direct_line.py`), świadomie **nie** przez nowszy
  Microsoft 365 Agents SDK (ten nie wspiera uwierzytelniania jednostki
  usługi bez zalogowanego użytkownika, czego worker właśnie potrzebuje).
  Sekret Direct Line czytany jest wyłącznie ze zmiennej środowiskowej
  (`PPDM_COPILOT_DIRECTLINE_SECRET`) i nigdy nie jest logowany. Odpowiedź
  agenta jest parsowana wyrażeniami regularnymi wyszukującymi trzy sekcje
  otoczone znacznikami `<<<TECHNICAL_DOCUMENTATION>>>...
  <<<END_TECHNICAL_DOCUMENTATION>>>` (analogicznie dla dokumentacji
  użytkownika i podsumowania zmian) — brakująca sekcja staje się po
  prostu pustym tekstem zamiast wywoływać błąd, żeby lekko niedoskonała
  odpowiedź agenta nie wywalała całego zadania.

## 9. Normalizacja, porównywanie wersji i ocena wpływu

### Znormalizowana reprezentacja

`worker/normalization/schema.py` definiuje jedyny kształt danych Power
Platform, który kiedykolwiek trafia do silnika porównującego albo do
promptu Copilota — **nigdy** surowy eksport ZIP (decyzja architektoniczna
ADR-007 w `DECISIONS.md`, m.in. żeby nie wysyłać do Copilota potencjalnie
wrażliwej, nadmiarowej zawartości surowego rozwiązania):

```json
{
  "schema_version": 1,
  "solution": {"name": "", "version": "", "publisher": "", "description": ""},
  "applications": [{"name": "", "type": "", "screens": [{"name": "", "controls_summary": ""}]}],
  "flows": [{"name": "", "trigger": "", "actions": [], "conditions": [], "timeout": null}],
  "tables": [],
  "environment_variables": [{"name": "", "type": "", "default_value": ""}],
  "connection_references": [{"name": "", "connector": ""}],
  "dependencies": [{"name": "", "type": ""}],
  "security": {"roles": []},
  "components": [{"name": "", "type": ""}]
}
```

Zasady determinizmu (kluczowe, żeby `git diff` na zrzutach i porównania
wersji były w ogóle sensowne): każda nazwana lista jest sortowana po
`name`; listy reprezentujące sekwencję kroków (akcje/warunki w flow) **nie
są** ponownie sortowane — ich autorska kolejność ma znaczenie; każdy
słownik ma ustalony, stały porządek kluczy niezależnie od kolejności w
danych wejściowych.

### Silnik różnic (diff)

`worker/diff/engine.py` porównuje dwa znormalizowane zrzuty **pole po
polu, per typ komponentu** — nigdy jako tekstowy/liniowy diff surowego
JSON-a. Wynik ma zawsze kształt:

```json
{
  "version_from": "1.0",
  "version_to": "1.1",
  "changes": [
    {"type": "ADDED", "component": "flow", "name": "Eskalacja faktury"},
    {"type": "MODIFIED", "component": "flow", "name": "Zatwierdzenie faktury",
     "details": ["timeout changed from 24h to 48h"]}
  ]
}
```

Typy zmian: `ADDED`, `REMOVED`, `MODIFIED`. Typy komponentów: `solution`,
`application`, `screen`, `flow`, `table`, `environment_variable`,
`connection_reference`, `dependency`, `security_role`, `component`.
Rejestrowanie nowej aplikacji od zera (`diff_for_initial_version()`)
porównuje ją po prostu z pustym zrzutem — dzięki czemu każdy komponent
naturalnie pojawia się jako „ADDED”, co jest właściwą semantyką dla
„to jest pierwsza dokumentowana wersja”.

### Ocena wpływu dokumentacyjnego

`worker/diff/impact.py` mapuje każdy wpis diffa na parę wartości
(wpływ techniczny, wpływ dla użytkownika) ze zbioru `{NONE, LOW, MEDIUM,
HIGH}`, **w pełni deterministycznie, bez żadnego wywołania AI** — to
zamierzone (zobacz `CLAUDE.md`: dostępność Copilota nigdy nie jest
gwarantowana, więc ocena wpływu musi działać sensownie bez niego zawsze;
Copilot może ją później dopracować, ale wynik deterministyczny jest
zawsze liczony jako pierwszy i jest autorytatywny, gdy dopracowanie AI
jest niedostępne).

Przykładowe reguły (pełna tabela w kodzie, `assess_change_impact()`):

| Komponent | Dodanie/usunięcie | Modyfikacja |
|---|---|---|
| flow (przepływ) | HIGH / HIGH | zależy od słów kluczowych: `log`/`error`/`diagnostic`/`telemetry` → LOW/NONE; `timeout`/`approval`/`escalat`/`notification` → MEDIUM/HIGH; zmiana wyzwalacza/warunku → MEDIUM/MEDIUM; dodanie/usunięcie akcji → MEDIUM/LOW; inaczej LOW/LOW |
| screen (ekran) | MEDIUM / HIGH | LOW / MEDIUM |
| application (aplikacja) | HIGH / HIGH | LOW / LOW |
| environment_variable | LOW / NONE | jak wyżej wg słów kluczowych |
| connection_reference | MEDIUM / NONE | LOW / NONE |
| security_role | zawsze MEDIUM / LOW | — |
| table (tabela) | HIGH / MEDIUM | MEDIUM / LOW |

Zestawione przykłady dokładnie odpowiadają wzorcowym scenariuszom z
oryginalnej specyfikacji projektu: „dodanie zmiennej do logowania” →
techniczny=LOW, użytkownika=NONE; „zmiana limitu czasu zatwierdzenia” →
techniczny=MEDIUM, użytkownika=HIGH; „dodanie nowego ekranu widocznego dla
użytkownika” → techniczny=MEDIUM, użytkownika=HIGH; „dodanie nowego
procesu biznesowego” (nowy flow) → techniczny=HIGH, użytkownika=HIGH.

## 10. Wersjonowanie dokumentacji

`worker/versioning/version.py` — prosta, jawna polityka:

- Pierwsza udokumentowana wersja aplikacji to zawsze **1.0**.
- Brak wykrytych zmian od ostatniej wersji → numer wersji **się nie
  zmienia**, nie powstaje nowy wpis w `DocumentationVersions`.
- Jakakolwiek wykryta zmiana (wpływ LOW, MEDIUM albo HIGH na
  którejkolwiek osi) → podbicie wersji **pomniejszej** (1.0 → 1.1 → 1.2…).
- Podbicie wersji **głównej** (np. 1.x → 2.0) jest **zawsze** świadomą,
  jawną decyzją administratora (`major=True`), **nigdy** automatycznie
  wnioskowaną z rozmiaru czy wagi zmian — uznano to za niewiarygodne
  źródło takiej decyzji (zobacz `DECISIONS.md`, jeśli ta polityka ma być
  kiedyś zmieniona).

## 11. Generowanie dokumentacji

`worker/documentation/generator.py` renderuje trzy artefakty Markdown na
podstawie kontekstu zbudowanego przez `JobProcessor`
(rekord aplikacji, znormalizowany zrzut, diff, ocena wpływu, wersje
`from`/`to`).

**Dokumentacja techniczna** (`render_technical_documentation`) — zawsze te
same sekcje, w tej samej kolejności, nawet jeśli treść jest skąpa (wtedy
sekcja zawiera po prostu „Not applicable.” zamiast być pominięta — to
świadoma decyzja, żeby konsumenci tej dokumentacji mogli polegać na
stabilnej strukturze): Overview, Architecture, Components, Power Apps,
Power Automate, Data Sources, Dependencies, Environment Variables,
Connection References, Security, Business Logic, Error Handling, ALM,
Deployment, Known Limitations.

**Przewodnik użytkownika** (`render_user_guide`) — sekcje: Purpose, Who
should use this application, How to open it, Main workflows, Step-by-step
usage, Expected behavior, Troubleshooting, FAQ.

**Podsumowanie zmian** (`render_change_summary`) — krótka lista w formacie
`Wersja: X (poprzednia: Y)` + wypunktowana lista zmian, każda linia
opisana po ludzku (np. `Changed flow "Zatwierdzenie faktury": timeout
changed from 24h to 48h`).

Te trzy funkcje są też wywoływane pośrednio przez `MockCopilotAdapter` —
tryb mockowy **nie jest atrapą treści**, tylko w pełni funkcjonalnym,
deterministycznym generatorem; różnica względem trybu z prawdziwym
Copilotem jest wyłącznie w tym, że tryb mockowy nie „dopisuje prozy” ani
nie interpretuje kontekstu swobodnie — działa wyłącznie na sztywnych
szablonach.

## 12. Integracja z Copilot

Pełny opis w `docs/COPILOT_INTEGRATION.md` (EN) oraz w rozdziale 9 dokumentu
`docs/KONFIGURACJA_SRODOWISKA_PRODUKCYJNEGO.md` (PL). W skrócie: Copilot
jest **opcjonalny, nigdy wymagany** — worker musi w pełni działać z
`HumanReviewCopilotAdapter` (albo `MockCopilotAdapter` lokalnie), bo
dostępność jakiegokolwiek konkretnego produktu/API Copilota nigdy nie jest
gwarantowana z góry. Zweryfikowano realnie, że programowe wywołanie
agenta Copilot Studio jest możliwe przez **Direct Line API**, bez
potrzeby Azure Bot Service, MCP czy jakiegokolwiek API Graph/Copilot —
jest to jednak zależne od aktywnej licencji/publikacji agenta (opisane
szczegółowo w rozdziale 9 dokumentu konfiguracyjnego).

## 13. Skrypty pomocnicze

| Skrypt | Co robi |
|---|---|
| `scripts/setup.sh` / `.ps1` | Tworzy lokalne środowisko wirtualne Python (`.venv`) i instaluje zależności testowe |
| `scripts/run-tests.sh` / `.ps1` | Uruchamia `pytest worker/tests` |
| `scripts/run-worker.sh` / `.ps1` | Ustawia domyślne tryby adapterów (mock, o ile nie nadpisane) i uruchamia `python -m worker.main` |
| `scripts/demo.py` (+ `.sh`/`.ps1`) | Pełne demo end-to-end na mockach: rejestruje aplikację „Invoice Approval”, dokumentuje ją jako wersję 1.0, potem przetwarza zmianę do wersji 1.1, wypisuje podsumowanie zmian i ścieżki do wszystkich wygenerowanych plików |
| `scripts/provision_sharepoint_graph.py` | Tworzy 4 listy SharePoint (z dokładnymi kolumnami z `sharepoint/lists/*.json`), kolumnę Lookup między listami oraz bibliotekę dokumentów z folderami — przez Microsoft Graph, w pełni idempotentnie (bezpiecznie uruchomić wielokrotnie) |

`scripts/demo.py` jest szczególnie przydatny do szybkiego sprawdzenia, że
zmiana w kodzie niczego nie zepsuła — pokazuje cały cykl: rejestracja →
dokumentacja v1.0 → wykrycie zmian v1.0→v1.1 → ocena wpływu →
regeneracja dokumentacji → aktualizacja historii wersji → podsumowanie
zmian, dokładnie tak samo, jak realny worker robiłby to na prawdziwej
dzierżawie.

## 14. Konfiguracja

Cała konfiguracja idzie przez zmienne środowiskowe czytane w
`worker/config.py` — **zero** sekretów, adresów URL czy identyfikatorów
dzierżawy zapisanych na sztywno gdziekolwiek w kodzie. Pełna lista zmiennych
i ich znaczenie jest w rozdziale 7 dokumentu
`docs/KONFIGURACJA_SRODOWISKA_PRODUKCYJNEGO.md`. Skrót: `PPDM_*_MODE`
wybiera tryb (mock/real/human_review) dla każdego z trzech adapterów
niezależnie; ustawienie trybu `real` bez uzupełnienia wymaganych zmiennych
zgłasza natychmiastowy, czytelny błąd zamiast ciche niepowodzenie później.

## 15. Bezpieczeństwo

Pełny model w `SECURITY.md` (EN); najważniejsze zasady po polsku są w
rozdziale 11 dokumentu konfiguracyjnego. Skrót skrótu: żadnych sekretów w
Git ani w wartościach list SharePoint; osobna, minimalnie uprawniona
tożsamość usługi dla workera; logi nigdy nie zawierają wartości sekretów
(tylko ich nazwy); Power Apps działa jako zalogowany użytkownik, worker
jako osobna tożsamość aplikacyjna — to dwie świadomie różne tożsamości.

## 16. Testowanie

```bash
./scripts/run-tests.sh
```

To uruchamia pełny zestaw testów `pytest worker/tests` — działa w pełni
offline, bez żadnego dostępu do prawdziwego SharePoint/Power Platform,
dzięki adapterom mockowym. Najważniejszy pojedynczy test to
`worker/tests/test_integration_pipeline.py` — pełny scenariusz
end-to-end: rejestracja aplikacji → dokumentacja v1.0 → wykrycie zmian
v1.0→v1.1 → ocena wpływu → regeneracja dokumentacji → aktualizacja
historii wersji → podsumowanie zmian. Ten test **nigdy nie powinien być
osłabiany**, żeby przepuścić inną, niezwiązaną zmianę — zamiast tego
naprawia się kod, który go psuje (zasada wyraźnie zapisana w `CLAUDE.md`).

Testy dotykające logiki zweryfikowanej na prawdziwej dzierżawie (nie
mockowej) są osobno oznaczone: `worker/tests/test_real_powerplatform_adapter.py`,
`worker/tests/test_real_powerplatform_parsing.py`,
`worker/tests/test_real_sharepoint_adapter.py`,
`worker/tests/test_real_copilot_adapter.py`,
`worker/tests/test_direct_line.py` — przejście tych testów potwierdza
tylko poprawność kodu parsującego/wywołującego, nie zastępuje faktycznego
uruchomienia przeciwko prawdziwemu systemowi (zasada: „nigdy nie twierdź,
że prawdziwa integracja działa, jeśli nie została faktycznie
przetestowana na prawdziwym systemie”).

## 17. Realnie napotkane i rozwiązane błędy

Ta sekcja to skondensowana lista rzeczywistych problemów napotkanych przy
uruchamianiu tego projektu przeciwko prawdziwej (testowej) dzierżawie —
przydatna, jeśli natrafisz na coś podobnego na swojej dzierżawie
produkcyjnej.

**Power Platform CLI / eksport rozwiązania:**
- `authenticate()` zawsze uruchamiał `pac auth create` (świeże logowanie)
  — nieszkodliwe przy jednorazowym, interaktywnym uruchomieniu, ale
  zawiesiłoby w nieskończoność workera działającego bez nadzoru, gdyby
  profil logowania dla danego środowiska już istniał. Naprawione funkcją
  `ensure_authenticated()`, która najpierw sprawdza `pac auth list` i
  wybiera istniejący profil, zamiast zakładać, że trzeba się zalogować
  ponownie.
- `pac solution export` domyślnie kończy się błędem, jeśli ścieżka
  docelowa już istnieje (brak nadpisywania) — psuje to każde ponowne
  uruchomienie na tym samym katalogu eksportu (np. ponowienie zadania po
  błędzie, albo kolejne zadanie `UPDATE_DOCUMENTATION` dla tej samej
  aplikacji). Naprawione dodaniem flagi `--overwrite`.
- Nazwy plików prawdziwych flow zawierają fragment identyfikatora GUID
  (np. `Button-Getitems-53E8B648-3F25-EE11-9965-6045BD0D0CC5.json`), a
  sam GUID zawiera wewnętrzne myślniki — pierwotny kod obcinający „nazwę
  techniczną” przez `rsplit("-", 1)` (odcięcie tylko ostatniego segmentu
  po myślniku) zostawiał większość GUID-a w nazwie używanej do
  porównywania wersji. Naprawione wyrażeniem regularnym dopasowującym
  pełny wzorzec GUID (8-4-4-4-12 znaków szesnastkowych).
- `job_processor.py` przekazywał do `pac` przyjazną etykietę środowiska
  (`Application.environment`, np. „DEV”) zamiast faktycznego adresu URL
  (`Application.environment_url`), którego `pac` naprawdę potrzebuje —
  opisane szerzej w rozdziale 7.

**SharePoint / Microsoft Graph:**
- Zapis jawnego `null` dla niewypełnionego pola typu `dateTime` przy
  tworzeniu elementu listy zwracał nieczytelny błąd HTTP 500. Naprawione
  przez pominięcie niewypełnionych pól w treści zapisu w ogóle (funkcja
  `_drop_none()`), zamiast wysyłania ich jako `null`.
- Zapis kolumny typu „Hiperłącze lub obraz” zawodził przy każdym
  wypróbowanym kształcie danych. Naprawione przejściem tych kolumn
  (`EnvironmentUrl`, `TechnicalDocumentationUrl`, `UserDocumentationUrl`)
  na zwykły typ tekstowy.
- Zapytanie o kolumny listy nie zwraca właściwości `hyperlinkOrPicture`
  dla kolumn tego typu, nawet dla poprawnie utworzonych kolumn — to
  udokumentowane zachowanie Graph, nie dowód błędnej konfiguracji.

**Power Apps (aplikacja canvas):**
- Przestarzały format `Experimental` (używany przez `pac canvas
  unpack/pack`) **nie potrafi** stworzyć od zera kontrolek wejściowych
  (np. `TextInput`) — działa tylko do edycji w miejscu już istniejącej,
  prawdziwej aplikacji.
- Nowszy format `SourceCode` działa, ale **tylko** gdy edytuje się już
  rozpakowaną, prawdziwą aplikację bazową — zbudowanie całego drzewa
  źródłowego od zera w tym formacie powoduje awarię pakowania
  (`System.FormatException`).
- Kolumny typu Wybór/Lookup/Osoba wymagają konkretnych, nieoczywistych
  kształtów obiektu przy zapisie przez `Patch()` — patrz rozdział 6.
- Kolizja nazwy ekranu z nazwą źródła danych powoduje ciche
  przemianowanie ekranu przez Studio i zepsucie formuł — patrz rozdział 6.
- Formuła odwołująca się do niepodłączonego źródła danych wygląda jak
  błąd typu — patrz rozdział 6.

## 18. Znane ograniczenia i rzeczy niedokończone

- `RealPowerPlatformAdapter.get_application_metadata()` zwraca puste
  listy dla tabel, zależności, ról bezpieczeństwa i ogólnych komponentów
  — żadna z dostępnych aplikacji testowych ich nie zawierała, więc
  parsowanie tych kategorii pozostaje niezweryfikowane wobec prawdziwego
  eksportu.
- Aplikacja canvas w formacie `SourceCode` (nowszy, zalecany przez `pac`
  format wymagający `MSAppStructureVersion ≥ 2.4.0`) nie została
  zweryfikowana jako **wynik** parsowania przez
  `RealPowerPlatformAdapter` — obie dostępne aplikacje testowe miały
  starszy format `Experimental`. Aplikacja wygenerowana w tym projekcie
  (`powerapps/generated/`) używa formatu `SourceCode`, ale została
  zbudowana i zweryfikowana ręcznie przez Power Apps Studio, nie przez
  automatyczne parsowanie w workerze.
- Kolumna `DocumentationJobs.Application` (typu Lookup) celowo **nie
  jest** zapisywana przez `RealSharePointAdapter.create_job()` —
  identyfikator aplikacji jest zamiast tego przechowywany jako osobny
  artefakt zadania (`_application_id.txt`), dopóki zapis pól typu
  Lookup/Osoba nie zostanie w pełni zweryfikowany end-to-end dla tej
  konkretnej ścieżki zapisu.
- Odczyt kolumn typu Osoba/Grupa z powrotem przez `RealSharePointAdapter`
  nie rozwiązuje identyfikatora z powrotem na adres e-mail — pola takie
  jak `Owner`/`RequestedBy` po odczycie są puste, mimo że mają ustawioną
  wartość (luka kosmetyczna, nieużywana przez żadną logikę biznesową).
- Prawdziwa jednoczesna próba przejęcia tego samego zadania przez dwóch
  worker'ów w tej samej chwili nie została odtworzona w praktyce — logika
  optymistycznej współbieżności (etag) jest poprawna zgodnie z
  udokumentowanym zachowaniem Graph, ale nie była realnie „wyścigowo”
  przetestowana.
- Host produkcyjny (maszyna, harmonogram, tożsamość usługi) nie jest
  jeszcze wybrany — patrz `docs/DEPLOYMENT.md` i rozdział 10 dokumentu
  konfiguracyjnego.
