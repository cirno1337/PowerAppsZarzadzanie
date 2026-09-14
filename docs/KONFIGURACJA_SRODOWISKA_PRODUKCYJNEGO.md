# Konfiguracja środowiska produkcyjnego (PL)

Ten dokument opisuje krok po kroku, jak uruchomić **Power Platform
Documentation Manager** na prawdziwej (nie testowej/mockowej) dzierżawie
Microsoft 365 / Power Platform — od zera do działającego workera, który
faktycznie dokumentuje aplikacje Power Platform i zapisuje wyniki w
SharePoint.

Wszystko, co jest tu opisane, zostało **realnie sprawdzone** na osobistej,
testowej dzierżawie Power Platform (nie na dzierżawie firmowej) — wszystkie
adaptery „real” (`RealPowerPlatformAdapter`, `RealSharePointAdapter`,
`RealCopilotAdapter`) zostały uruchomione end-to-end przeciwko prawdziwemu
SharePoint i prawdziwemu środowisku Power Platform. Poniższe kroki są więc
zweryfikowaną instrukcją, a nie tylko teorią — z zastrzeżeniem, że nazwy
dzierżawy, witryny i adresy URL poniżej są **celowo** zapisane jako
placeholdery (`<nazwa-dzierżawy>`, `<nazwa-witryny>` itd.), zgodnie z zasadą
tego repozytorium, żeby nigdy nie trzymać w Git realnych identyfikatorów
klienta (patrz `CLAUDE.md`, sekcja „Do not do”).

> **Uwaga o zrzutach ekranu**: w tym dokumencie celowo nie umieszczono
> zrzutów ekranu z rzeczywistej dzierżawy testowej użytej do weryfikacji —
> zawierałyby one nazwę tej dzierżawy i witryny, a repozytorium ma zasadę
> „żadnych identyfikatorów najemcy (tenant) w kodzie ani dokumentacji”.
> Zamiast tego każdy krok opisuje dokładnie, co powinno być widoczne na
> ekranie, żebyś mógł to zweryfikować u siebie. Jeśli chcesz, mogę
> przygotować zrzuty ekranu z Twojej własnej dzierżawy jako osobne pliki
> (poza repozytorium Git) — wystarczy poprosić.

## Spis treści

1. [Czego potrzebujesz zanim zaczniesz](#1-czego-potrzebujesz-zanim-zaczniesz)
2. [Krok 1 — Środowisko Power Platform](#2-krok-1--środowisko-power-platform)
3. [Krok 2 — Witryna SharePoint i listy](#3-krok-2--witryna-sharepoint-i-listy)
4. [Krok 3 — Rejestracja aplikacji Azure AD (Microsoft Graph)](#4-krok-3--rejestracja-aplikacji-azure-ad-microsoft-graph)
5. [Krok 4 — Aplikacja Power Apps](#5-krok-4--aplikacja-power-apps)
6. [Krok 5 — Power Automate (opcjonalnie)](#6-krok-5--power-automate-opcjonalnie)
7. [Krok 6 — Konfiguracja workera (.env)](#7-krok-6--konfiguracja-workera-env)
8. [Krok 7 — Pierwsze uruchomienie i test](#8-krok-7--pierwsze-uruchomienie-i-test)
9. [Krok 8 — Integracja z Copilot (opcjonalnie)](#9-krok-8--integracja-z-copilot-opcjonalnie)
10. [Krok 9 — Uruchomienie produkcyjne (host, harmonogram)](#10-krok-9--uruchomienie-produkcyjne-host-harmonogram)
11. [Bezpieczeństwo — najważniejsze zasady](#11-bezpieczeństwo--najważniejsze-zasady)
12. [Rozwiązywanie problemów](#12-rozwiązywanie-problemów)
13. [Checklist końcowy](#13-checklist-końcowy)

---

## 1. Czego potrzebujesz zanim zaczniesz

Zanim zaczniesz, zbierz poniższe informacje (patrz też
`docs/CORPORATE_SETUP.md`, Faza 1, w wersji angielskiej — ten dokument PL
jest jej praktycznym rozwinięciem):

- [ ] Adres URL środowiska Power Platform (np. `https://<środowisko>.crm4.dynamics.com`
      lub podobny — dokładny format zależy od regionu dzierżawy)
- [ ] Adres URL witryny SharePoint Online, na której mają powstać listy
      (np. `https://<nazwa-dzierżawy>.sharepoint.com/sites/<nazwa-witryny>`)
- [ ] Konto/tożsamość, na której będzie działał worker (na początek może
      to być Twoje własne konto administratora — docelowo powinna to być
      dedykowana tożsamość usługi o minimalnych uprawnieniach, patrz sekcja
      11)
- [ ] Uprawnienia administratora Azure AD / Entra wystarczające do
      utworzenia rejestracji aplikacji (App Registration) i nadania jej
      zgody administratora (admin consent)
- [ ] Zainstalowany Python 3.11+ na maszynie, na której uruchomisz workera
- [ ] Zainstalowany Power Platform CLI (`pac`) — patrz Krok 1
- [ ] Dostęp do Power Apps Studio (make.powerapps.com) w docelowym
      środowisku

Cały ten projekt jest zaprojektowany tak, aby **nie wymagać** Dataverse,
konektorów Premium/niestandardowych, konektora HTTP w Power Automate ani
żadnych płatnych usług poza standardową licencją Microsoft 365 / Power
Platform — patrz `CLAUDE.md`, sekcja „Hard constraint”. Jeśli którykolwiek
z poniższych kroków zdaje się tego wymagać, zatrzymaj się i sprawdź jeszcze
raz — to nie jest zamierzone.

---

## 2. Krok 1 — Środowisko Power Platform

### 2.1 Instalacja `pac` CLI

```bash
# przez .NET Tool (zweryfikowane, działa na Linux/macOS/Windows)
dotnet tool install --global Microsoft.PowerApps.CLI.Tool
pac --version
```

**Ważne, realnie zweryfikowane spostrzeżenie**: pakiet npm
`@microsoft/powerplatform-cli`, który bywa sugerowany w starszych
poradnikach, **już nie istnieje**. Jedyne oficjalnie wspierane metody
instalacji to: rozszerzenie VS Code, .NET Tool (jak wyżej) oraz instalator
MSI dla Windows. Nie próbuj `npm install` — to nie zadziała. Zweryfikowana
wersja podczas prac nad tym projektem: `pac` 2.12.2 (wymaga zainstalowanego
.NET SDK; na Linuksie dodatkowo pakietu `aspnet-runtime`).

### 2.2 Logowanie

```bash
pac auth create --url <adres-URL-środowiska>
```

Jeśli logujesz się na maszynie bez przeglądarki (np. przez SSH), użyj
logowania kodem urządzenia — **zweryfikowane, działa dobrze**:

```bash
pac auth create --deviceCode --url <adres-URL-środowiska>
```

Sprawdź, że logowanie działa:

```bash
pac auth list
pac org list
pac solution list --environment <adres-URL-środowiska>
```

### 2.3 Czego `pac` NIE wolno używać w tym projekcie

Worker tego projektu **tylko eksportuje i odczytuje** dane — nigdy nie
importuje ani nie modyfikuje środowiska. Nie uruchamiaj (bez wyraźnej,
świadomej decyzji administracyjnej):

- `pac solution import` — wgrywa rozwiązanie do środowiska
- `pac solution publish-all` ani żadnej komendy `pac admin` zarządzającej
  cyklem życia środowiska (tworzenie/usuwanie/reset/kopiowanie)
- niczego pod `pac data`, co zapisuje dane

Bezpieczne (tylko odczyt/eksport), których worker faktycznie używa:

```bash
pac solution export --name <nazwa-rozwiązania> --environment <URL> --path ./export --managed false --overwrite
pac solution unpack --zipfile ./export/<rozwiązanie>.zip --folder ./unpacked --packagetype Unmanaged
```

---

## 3. Krok 2 — Witryna SharePoint i listy

Worker potrzebuje czterech list SharePoint w jednej witrynie: `Applications`,
`DocumentationJobs`, `DocumentationVersions` oraz opcjonalnie
`Configuration`, a także biblioteki dokumentów `PowerPlatformDocumentation`.
Dokładne definicje kolumn są w `sharepoint/lists/*.json` — to jest
jedyne źródło prawdy, z którego korzysta zarówno skrypt provisioningu, jak
i `RealSharePointAdapter`.

Masz trzy opcje, w kolejności zalecanej:

### Opcja A (zalecana): skrypt `scripts/provision_sharepoint_graph.py`

To jest metoda **realnie zweryfikowana end-to-end** na testowej dzierżawie
— utworzyła wszystkie 4 listy z dokładnymi kolumnami, kolumnę przeglądową
(lookup) `Application` między listami, bibliotekę dokumentów
`PowerPlatformDocumentation` wraz z folderami `_jobs`, `_templates`,
`_logs`. Skrypt jest idempotentny — bezpiecznie uruchomić go ponownie
(przy konflikcie 409 używa istniejącego obiektu zamiast się wywalać).

Wymaga rejestracji aplikacji Azure AD z uprawnieniem Graph
`Sites.Manage.All` — opisane w Kroku 3 poniżej. Uruchom Krok 3 **przed**
tym krokiem.

```bash
pip install msal requests
# albo:
pip install -e ".[provisioning]"
```

Utwórz lokalny, ignorowany przez Git plik `.env` w katalogu głównym
repozytorium (skrypt provisioningu czyta **inne** nazwy zmiennych niż sam
worker — to celowe, żeby dane logowania jednorazowego provisioningu nigdy
nie były tymi samymi danymi, na których worker działa długoterminowo):

```bash
TENANT_ID=<id-dzierżawy>
CLIENT_ID=<id-aplikacji-azure-ad>
CLIENT_SECRET=<sekret-kliencki>
SHAREPOINT_SITE_URL=https://<nazwa-dzierżawy>.sharepoint.com/sites/<nazwa-witryny>
```

Uruchom:

```bash
python scripts/provision_sharepoint_graph.py
```

Skrypt wypisze, co utworzył. Sprawdź w przeglądarce, w witrynie SharePoint
→ **Zawartość witryny**, że widzisz 4 listy (`Applications`, `Configuration`,
`DocumentationJobs`, `DocumentationVersions`) oraz bibliotekę dokumentów
`PowerPlatformDocumentation` z podfolderami `_jobs`, `_templates`, `_logs`.

**Znana, udokumentowana „dziwność” API Graph** (to nie błąd): zapytanie
`GET .../lists/{id}/columns` nie zwraca właściwości `hyperlinkOrPicture`
dla kolumn tego typu, nawet jeśli kolumna została utworzona poprawnie —
jeśli to zobaczysz przy weryfikacji, to oczekiwane zachowanie Graph, a nie
dowód błędu.

### Opcja B: skrypt PowerShell (PnP)

`sharepoint/provisioning/provision-lists.ps1` — czyta te same definicje
JSON i tworzy listy/kolumny/bibliotekę przez moduł
[PnP.PowerShell](https://pnp.github.io/powershell/). **Nieprzetestowany na
prawdziwej dzierżawie w ramach tego projektu** — przejrzyj go przed
uruchomieniem i wypróbuj najpierw na środowisku nieprodukcyjnym.

### Opcja C: ręczne utworzenie przez interfejs SharePoint

Najbardziej pracochłonne, ale zero ryzyka związanego ze skryptem — dobra
opcja na pierwsze podejście, jeśli wolisz mieć pełną kontrolę. Użyj plików
`sharepoint/lists/*.json` jako listy kontrolnej: dla każdej listy utwórz
dokładnie te kolumny, z dokładnie tymi typami i nazwami (patrz uwaga
poniżej o nazwach wewnętrznych).

**Kroki w interfejsie**:
1. Otwórz witrynę SharePoint → **Zawartość witryny** → **Nowy** → **Lista**.
2. Nadaj liście nazwę dokładnie taką, jak w pliku JSON (`Applications`,
   `DocumentationJobs`, `DocumentationVersions`, `Configuration`).
3. Dla każdej kolumny z pliku JSON: **Dodaj kolumnę** → wybierz typ zgodny
   z polem `"type"` w JSON (np. „Pojedynczy wiersz tekstu”, „Wybór”, „Osoba
   lub grupa”, „Data i godzina”, „Tak/Nie”, „Liczba”) → dla kolumn typu
   „Wybór” wpisz dokładnie wartości z pola `"choices"`.
4. Dla kolumny `Application` (typ Lookup w listach `DocumentationJobs` i
   `DocumentationVersions`) wybierz jako źródło listę `Applications`,
   kolumnę `Title`.
5. Utwórz bibliotekę dokumentów **PowerPlatformDocumentation**
   (Zawartość witryny → Nowy → Biblioteka dokumentów), a w niej trzy
   foldery: `_jobs`, `_templates`, `_logs`.

### 3.1 Ważne: nazwy kolumn bez spacji

SharePoint czasem przepisuje **wewnętrzną** nazwę kolumny (używaną przez
API) inaczej niż nazwę wyświetlaną — najczęściej gdy nazwa wyświetlana
zawiera spację (np. „Application Id” może dostać wewnętrzną nazwę
`Application_x0020_Id`). Dlatego wszystkie nazwy kolumn w tym projekcie są
jednowyrazowe/PascalCase, bez spacji (`ApplicationId`, nie „Application
Id”) — trzymaj się tego również przy ręcznym tworzeniu list.

### 3.2 Dlaczego kolumny adresów URL to zwykły tekst, nie „Hiperłącze”

Kolumny `EnvironmentUrl`, `TechnicalDocumentationUrl` i
`UserDocumentationUrl` są zdefiniowane jako zwykły **„Pojedynczy wiersz
tekstu”**, a nie typ „Hiperłącze lub obraz”. To świadoma decyzja: przy
realnym testowaniu zapis do kolumny typu „Hiperłącze lub obraz” przez
Microsoft Graph zawodził przy każdym wypróbowanym kształcie danych (zwykły
tekst, udokumentowany obiekt `{"Url":..., "Description":...}` w obu
wariantach wielkości liter) — przyczyna nie została ustalona, a obejściem
było przejście na zwykły tekst. Jeśli tworzysz te kolumny ręcznie, użyj
typu tekstowego, nie „Hiperłącze”.

---

## 4. Krok 3 — Rejestracja aplikacji Azure AD (Microsoft Graph)

Worker (a właściwie `RealSharePointAdapter`) łączy się z SharePoint przez
Microsoft Graph, uwierzytelniając się jako aplikacja (client credentials
flow, bez zalogowanego użytkownika) — nie przez konto użytkownika. Wymaga
to rejestracji aplikacji w Azure AD / Entra.

1. Wejdź do **Entra admin center** (`entra.microsoft.com`) →
   **Rejestracje aplikacji** → **Nowa rejestracja**.
2. Nadaj nazwę (np. „PPDM Worker” lub „PPDM Provisioning” — jeśli
   rozdzielasz tożsamość jednorazowego provisioningu od docelowej tożsamości
   workera, zrób to jako dwie osobne rejestracje, patrz sekcja 11).
3. **Uprawnienia interfejsu API** → **Dodaj uprawnienie** →
   **Microsoft Graph** → **Uprawnienia aplikacji** (nie delegowane, bo
   worker działa bez zalogowanego użytkownika):
   - do jednorazowego provisioningu list: `Sites.Manage.All`
   - do docelowej, długoterminowej tożsamości workera (patrz sekcja 11,
     zasada najmniejszych uprawnień): rozważ węższe `Sites.Selected` +
     nadanie dostępu tylko do konkretnej witryny, zamiast całej dzierżawy
4. Kliknij **Udziel zgody administratora dla `<dzierżawa>`** — bez tego
   uprawnienia aplikacji nie zadziałają, nawet jeśli są dodane na liście.
5. **Certyfikaty i sekrety** → **Nowy sekret kliencki** → skopiuj wartość
   **natychmiast** (nie będzie widoczna ponownie) i wklej ją do lokalnego
   `.env` — nigdy do żadnego pliku śledzonego przez Git.
6. Zapisz z ekranu **Przegląd**: **Identyfikator aplikacji (klienta)** oraz
   **Identyfikator katalogu (dzierżawy)** — to Twoje `CLIENT_ID` i
   `TENANT_ID`.

---

## 5. Krok 4 — Aplikacja Power Apps

Masz dwie ścieżki. Zalecana jest ścieżka A — to gotowy plik `.msapp`,
który w tym projekcie został już zbudowany, w pełni ręcznie
przetestowany i zweryfikowany jako działający bez błędów na wszystkich
9 ekranach na prawdziwej dzierżawie testowej.

### Ścieżka A (zalecana): import gotowego pliku `.msapp`

Plik `powerapps/generated/PPDM.msapp` w tym repozytorium to kompletna,
9-ekranowa aplikacja canvas, gotowa do zaimportowania. Zawiera ekrany:
Pulpit (Dashboard), Lista aplikacji, Szczegóły aplikacji, Rejestracja
aplikacji, Żądanie dokumentacji, Żądanie aktualizacji, Historia wersji,
Historia zadań, Diagnostyka administratora.

1. Wejdź na **make.powerapps.com**, upewnij się, że jesteś w docelowym
   środowisku produkcyjnym (selektor środowiska w prawym górnym rogu).
2. **Aplikacje** → **Importuj aplikację** → **Z pliku (.msapp)** → wskaż
   `powerapps/generated/PPDM.msapp`.
3. **Kluczowy krok — ponowne podłączenie źródeł danych**: ten plik
   `.msapp` został wyeksportowany z innej (testowej) dzierżawy i ma w
   środku zapisane odwołania do list SharePoint tamtej dzierżawy. Podczas
   importu Power Apps pokaże ekran **„Przejrzyj połączenia z danymi”**
   (Review data source connections) — dla każdego z 4 źródeł
   (`Applications`, `Configuration`, `DocumentationJobs`,
   `DocumentationVersions`) wybierz **swoją** witrynę SharePoint i
   odpowiadającą jej listę utworzoną w Kroku 2. Jeśli ten ekran nie
   pojawi się automatycznie, otwórz aplikację po imporcie w Studio →
   **Widok** → **Źródła danych** i ręcznie zamień każde źródło na listę w
   Twojej witrynie.
4. Zapisz i opublikuj aplikację (**Plik** → **Zapisz**, potem
   **Opublikuj**).
5. Udostępnij aplikację docelowej grupie użytkowników (**Udostępnij**) —
   Power Apps używa uprawnień SharePoint zalogowanego użytkownika, nie
   współdzielonej tożsamości usługi, więc każdy użytkownik potrzebuje
   własnych uprawnień do list (przynajmniej odczyt/zapis na
   `Applications` i `DocumentationJobs`).

**Realnie napotkane i rozwiązane problemy przy budowie tej aplikacji**
(dla informacji, gdybyś chciał ją modyfikować w Studio — pełny opis w
`docs/DOKUMENTACJA_TECHNICZNA.md`, rozdział o aplikacji Power Apps):

- Kolumny typu **Wybór** (Choice) trzeba zapisywać przez `Patch()` jako
  `{Value: "...", Id: 0, '@odata.type': "#Microsoft.Azure.Connectors.SharePoint.SPListExpandedChoice"}`
  — sam tekst nie wystarczy.
- Kolumny typu **Lookup** (np. `Application` w `DocumentationJobs`) trzeba
  zapisywać jako `{Id: <numer>, Value: <tekst>}`, nie całym powiązanym
  rekordem.
- Kolumny typu **Osoba/Grupa** wymagają pełnego obiektu z polem
  `'@odata.type': "#Microsoft.Azure.Connectors.SharePoint.SPListExpandedUser"`.
- **Nazwa ekranu w aplikacji nigdy nie może być identyczna z nazwą źródła
  danych** — inaczej Studio po cichu zmieni nazwę ekranu i przepisze
  formuły tak, by wskazywały na (przemianowany) ekran zamiast na listę,
  co psuje każdą formułę używającą tej nazwy. Dlatego ekran listy
  aplikacji nazywa się w tym projekcie `ApplicationsScreen`, nie
  `Applications`.
- Jeśli po imporcie jakiś ekran pokazuje błędy typu na formułach
  odwołujących się do listy — sprawdź najpierw, czy ta lista rzeczywiście
  jest podłączona jako źródło danych w panelu **Dane** w Studio (**Widok**
  → **Dane**). Brak podłączonego źródła powoduje, że każda formuła go
  używająca pokazuje się jako błąd typu, co bardzo przypomina błąd
  składni, a wcale nim nie jest.

### Ścieżka B: budowa ręczna od zera

Jeśli wolisz zbudować aplikację samodzielnie (np. żeby lepiej ją poznać,
albo dopasować wygląd), pełna specyfikacja ekran po ekranie, wraz z
gotowymi formułami Power Fx, jest w `powerapps/README.md` (w języku
angielskim). Podłącz aplikację do czterech list SharePoint jako źródeł
danych i zbuduj 9 ekranów opisanych w tamtym dokumencie.

---

## 6. Krok 5 — Power Automate (opcjonalnie)

Ta część jest **opcjonalna** — worker działa w pełni bez żadnych flow;
Power Automate służy tylko do powiadomień (np. e-mail o zmianie statusu
zadania), nigdy nie jest kolejką zadań (zobacz ADR-003 w `DECISIONS.md`:
SharePoint, konkretnie kolumna `DocumentationJobs.Status`, jest jedynym
źródłem prawdy o stanie zadania — awaria flow nie wpływa na przetwarzanie
zadań).

Specyfikacja trzech opcjonalnych flow (powiadomienie o statusie zadania,
przypomnienie o zawieszonym zadaniu, powiadomienie o nowej rejestracji
aplikacji) jest w `powerautomate/README.md`. Używają wyłącznie
standardowych konektorów SharePoint i Office 365 Outlook — **nigdy**
konektora HTTP ani Premium.

---

## 7. Krok 6 — Konfiguracja workera (.env)

Skopiuj szablon:

```bash
cp config/.env.example .env
```

Uzupełnij `.env` w katalogu głównym repozytorium (ten plik jest w
`.gitignore` — nigdy go nie commituj):

```bash
# --- Wybór trybu adapterów: "mock" | "real" (dla Copilota dodatkowo "human_review")
PPDM_POWERPLATFORM_MODE=real
PPDM_SHAREPOINT_MODE=real
PPDM_COPILOT_MODE=mock          # patrz Krok 8, jeśli chcesz włączyć real/human_review

# --- Wymaga konfiguracji dzierżawy
PPDM_SHAREPOINT_SITE_URL=https://<nazwa-dzierżawy>.sharepoint.com/sites/<nazwa-witryny>
PPDM_POWERPLATFORM_ENVIRONMENT_URL=<adres-URL-środowiska-Power-Platform>

# --- Rejestracja aplikacji Azure AD z Kroku 3 (docelowa tożsamość workera,
#     NIE koniecznie ta sama co do jednorazowego provisioningu list)
PPDM_SHAREPOINT_TENANT_ID=<id-dzierżawy>
PPDM_SHAREPOINT_CLIENT_ID=<id-aplikacji>
PPDM_SHAREPOINT_CLIENT_SECRET=<sekret-kliencki>

# --- Tożsamość i zachowanie workera
PPDM_WORKER_ID=produkcja-worker-01
PPDM_MAX_RETRIES=3
PPDM_POLL_INTERVAL_SECONDS=5
PPDM_VERBOSE_LOGGING=false
```

Wszystkie nazwy zmiennych są zdefiniowane w `worker/config.py` — to
jedyne miejsce, które je czyta; nic w repozytorium nie ma nigdzie
zaszytych na sztywno adresów URL ani identyfikatorów dzierżawy (patrz
`CLAUDE.md`).

Ustawienie dowolnego z `PPDM_*_MODE` na `real` bez uzupełnienia
wymaganych zmiennych (np. `PPDM_SHAREPOINT_MODE=real` bez
`PPDM_SHAREPOINT_TENANT_ID`) zgłasza od razu czytelny błąd
(`ValueError`) z listą brakujących zmiennych — `worker/adapters/factory.py`
sprawdza to przy starcie, zanim worker zacznie cokolwiek robić.

---

## 8. Krok 7 — Pierwsze uruchomienie i test

**Nie testuj od razu na prawdziwej aplikacji produkcyjnej.** Wybierz małe,
nieistotne rozwiązanie testowe (albo utwórz jedno specjalnie do tego celu).

1. Zainstaluj zależności:
   ```bash
   ./scripts/setup.sh
   ```
2. Uruchom testy jednostkowe (te działają w pełni offline, na mockach —
   potwierdzają, że sam kod jest poprawny, zanim dotkniesz prawdziwej
   dzierżawy):
   ```bash
   ./scripts/run-tests.sh
   ```
3. Zarejestruj testową aplikację — najprościej przez samą aplikację Power
   Apps (ekran „Rejestracja aplikacji”), podając nazwę rozwiązania
   (`SolutionName`), które faktycznie istnieje w docelowym środowisku
   Power Platform.
4. W aplikacji Power Apps, na ekranie szczegółów aplikacji, kliknij
   „Żądaj dokumentacji” — to utworzy wiersz w liście `DocumentationJobs`
   ze statusem `PENDING`.
5. Uruchom workera jednorazowo:
   ```bash
   ./scripts/run-worker.sh --once
   ```
6. Sprawdź:
   - [ ] zadanie w `DocumentationJobs` zmieniło status na `COMPLETED`
         (lub, jeśli coś poszło nie tak, `FAILED`/`NEEDS_HUMAN_REVIEW` —
         zobacz `ErrorMessage` w tym samym wierszu)
   - [ ] w bibliotece `PowerPlatformDocumentation/<Nazwa
         aplikacji>/1.0/` pojawiły się pliki: `snapshot.json`,
         `solution-info.json`, `diff.json`, `technical-documentation.md`,
         `user-guide.md`
   - [ ] wiersz w `Applications` zaktualizował się (`CurrentVersion`,
         `DocumentationStatus`, linki do dokumentacji)
   - [ ] pojawił się nowy wiersz w `DocumentationVersions`
   - [ ] **nigdzie** — ani w logach, ani w wygenerowanej dokumentacji, ani
         w wartościach list SharePoint — nie widać żadnego hasła, sekretu
         ani tokenu

Dopiero po czystym przejściu tego testu na nieprodukcyjnym rozwiązaniu
rozważ zarejestrowanie prawdziwej aplikacji produkcyjnej.

---

## 9. Krok 8 — Integracja z Copilot (opcjonalnie)

Worker w pełni działa **bez** Copilota — `PPDM_COPILOT_MODE=mock`
generuje dokumentację deterministycznie, na podstawie szablonów (zobacz
`worker/documentation/generator.py`), bez żadnego wywołania sieciowego.
To jest bezpieczny wybór domyślny.

Jeśli chcesz, aby treść dokumentacji była generowana/dopracowywana przez
Copilota, masz dwie opcje:

### Opcja 1: `human_review` (bez integracji API)

```bash
PPDM_COPILOT_MODE=human_review
```

Worker zapisze gotowy prompt do pliku `_jobs/<id-zadania>/copilot-prompt.md`
w bibliotece dokumentów, ustawi zadanie na status `NEEDS_HUMAN_REVIEW`, a
Ty (lub inny administrator) wklejasz ten prompt ręcznie do dowolnego
zatwierdzonego przez firmę narzędzia Copilot, a wynik podajesz z powrotem
programowo przez `JobProcessor.resume_needs_human_review(job_id,
human_result)`.

### Opcja 2: `real` — Copilot Studio przez Direct Line API

**Realnie zweryfikowane ustalenie**: wywołanie agenta Copilot Studio
programowo, bez zalogowanego użytkownika, jest możliwe przez **Direct
Line API** — nie trzeba Azure Bot Service, MCP ani żadnego API
Graph/Copilot. To jest **celowo nie** nowsze Microsoft 365 Agents SDK —
ten SDK, zgodnie z dokumentacją Microsoftu, nie wspiera uwierzytelniania
jednostki usługi (service principal) bez interaktywnego logowania, którego
worker właśnie potrzebuje.

1. W Copilot Studio otwórz swojego agenta → **Ustawienia** →
   **Zabezpieczenia** → **Zabezpieczenia kanału Web** (kanał obecnie nazywa
   się „Aplikacja natywna” w polskim interfejsie).
2. Skopiuj jeden z dwóch dostępnych sekretów.
3. **Opublikuj agenta** — bez publikacji Direct Line zwróci błąd HTTP 404
   przy próbie rozpoczęcia rozmowy, mimo że sam sekret jest poprawny
   (to realnie napotkany scenariusz: backend bota po prostu nie działa,
   dopóki agent nie zostanie opublikowany).
4. Ustaw w `.env`:
   ```bash
   PPDM_COPILOT_MODE=real
   PPDM_COPILOT_DIRECTLINE_SECRET=<sekret-z-kroku-2>
   ```

**Uwaga o licencjonowaniu**: sama mechanika Direct Line działa niezależnie
od tego, czy licencja/limit Copilot Credits jest aktywny — ale bez
wykupionej/nieprzeterminowanej licencji Copilot Studio proces publikacji
agenta może się nie udać z błędem rozliczeniowym. Sprawdź to w **Microsoft
365 admin center → Rozliczenia → Licencje**, konkretnie miejsca Copilot
Studio, zanim uznasz tę ścieżkę za gotową do produkcji. Pełny opis
weryfikacji jest w `docs/COPILOT_INTEGRATION.md` (po angielsku).

---

## 10. Krok 9 — Uruchomienie produkcyjne (host, harmonogram)

Worker jest celowo niezależny od konkretnego hosta — cała konfiguracja
idzie przez zmienne środowiskowe, bez żadnych założeń specyficznych dla
systemu operacyjnego w kodzie `worker/`. Musisz jednak sam zdecydować,
**gdzie** i **jak często** worker ma działać — to repozytorium nie
narzuca tej decyzji.

### Dwa tryby uruchomienia

```bash
python -m worker.main --once   # przetwarza maksymalnie jedno oczekujące zadanie i kończy działanie
python -m worker.main          # ciągła pętla odpytywania (Ctrl+C, żeby zatrzymać)
```

`--once` pasuje do harmonogramu (zaplanowane zadanie/cron uruchamiane co
kilka minut); tryb ciągły pasuje do procesu działającego stale (usługa
systemd, usługa Windows).

### Warianty hosta (wybierz jeden, żaden nie jest tu z góry narzucony)

| Wariant | Zalety | Wady |
|---|---|---|
| Maszyna Windows, Harmonogram zadań uruchamiający `run-worker.ps1 ... --once` cyklicznie | Prosty, pasuje do środowisk „Windows/PowerShell” | Ręczne skalowanie/monitoring |
| Maszyna Windows, proces ciągły `python -m worker.main` jako usługa (np. przez NSSM) | Ciągłe odpytywanie, prostszy model operacyjny niż zadanie cykliczne | Wymaga konta usługi z trwałym logowaniem |
| Serwer Linux, usługa systemd lub cron | Te same kompromisy co dla Windows, jeśli masz dostęp do Linuksa | Zależy od standardów firmy |
| Kontener (jeśli firma już ma infrastrukturę kontenerową) | Przenośny, łatwy redeploy | Sensowny tylko jeśli infrastruktura kontenerowa już istnieje — nie wprowadzaj Dockera wyłącznie dla tego projektu bez zgody |

### Lista kontrolna przed „prawdziwym” produkcyjnym uruchomieniem

- [ ] Tożsamość usługi workera ma **minimalne** wymagane uprawnienia (patrz
      sekcja 11), nie te same szerokie uprawnienia co jednorazowy
      provisioning list
- [ ] Sekrety (`PPDM_SHAREPOINT_CLIENT_SECRET`,
      `PPDM_COPILOT_DIRECTLINE_SECRET`) trzymane w mechanizmie sekretów
      danego hosta (Menedżer poświadczeń Windows, zmienne środowiskowe
      usługi systemd + uprawnienia pliku, Key Vault itp.), nie w zwykłym
      pliku `.env` leżącym gdziekolwiek dostępnym
- [ ] Ustalono politykę retencji/kopii zapasowych (SharePoint ma własne
      wersjonowanie list i bibliotek — sprawdź, czy to wystarcza, zamiast
      zakładać, że tak jest)
- [ ] Ustalono próg alarmowania dla zadań utkniętych w `FAILED` lub
      `NEEDS_HUMAN_REVIEW`
- [ ] Ustalono, kto jest odpowiedzialny za to narzędzie na co dzień
      (właściciel, zespół wsparcia)

Pełna, angielskojęzyczna checklist fazowa (9 faz, od zbierania informacji
po gotowość produkcyjną) jest w `docs/CORPORATE_SETUP.md` — ten
dokument PL jest jej praktycznym, gotowym do wykonania rozwinięciem.

---

## 11. Bezpieczeństwo — najważniejsze zasady

Skrót z `SECURITY.md` (pełna wersja po angielsku):

- **Nigdy nie trzymaj sekretów w Git** — ani w kodzie, ani w plikach
  konfiguracyjnych, ani w wartościach list SharePoint, ani w promptach do
  Copilota, ani w wygenerowanej dokumentacji.
- **Zasada minimalnych uprawnień**: tożsamość usługi workera powinna mieć
  na SharePoint tylko uprawnienie „Współtworzenie” (Contribute) na
  konkretnej witrynie/listach/bibliotece — nie dostęp administratora
  całej dzierżawy. Rozważ uprawnienie Graph `Sites.Selected` zamiast
  `Sites.Manage.All` dla docelowej, długoterminowej tożsamości (to drugie
  jest wygodne tylko do jednorazowego provisioningu).
- **Rozdziel tożsamości**: sekret użyty do jednorazowego utworzenia list
  (Krok 2/3) nie powinien być tym samym sekretem, na którym worker działa
  długoterminowo w produkcji.
- **Logi nigdy nie zawierają sekretów** — `worker/logging_setup.py` loguje
  nazwy zmiennych środowiskowych, nigdy ich wartości; pełna treść
  promptów/odpowiedzi Copilota nie jest logowana na poziomie INFO.
- **Power Apps a worker to dwie różne tożsamości**: aplikacja Power Apps
  działa jako zalogowany użytkownik (jego własne uprawnienia SharePoint),
  a worker działa jako osobna tożsamość aplikacyjna (Krok 3) — to
  zamierzone i nie trzeba (ani nie należy) tego ujednolicać.

---

## 12. Rozwiązywanie problemów

Pełna wersja po angielsku: `docs/TROUBLESHOOTING.md`. Najczęstsze
sytuacje napotkane realnie podczas prac nad tym projektem:

- **`ModuleNotFoundError: No module named 'worker'`** — uruchamiasz
  `pytest`/`python -m worker.main` nie z katalogu głównego repozytorium.
  Zawsze uruchamiaj z katalogu głównego.
- **Zadanie utknęło w `NEEDS_HUMAN_REVIEW`** — pobierz plik
  `_jobs/<id-zadania>/copilot-prompt.md` z biblioteki dokumentów, uruchom
  go w zatwierdzonym przez firmę narzędziu Copilot, a wynik przekaż przez
  `JobProcessor.resume_needs_human_review(job_id, human_result)`.
- **Ekran w Power Apps pokazuje błędy typu na formułach, które wyglądają
  poprawnie** — sprawdź najpierw (**Widok → Dane**), czy dana lista
  SharePoint jest w ogóle podłączona jako źródło danych. Brak podłączenia
  wygląda identycznie jak błąd typu/składni.
- **`pac solution export` zgłasza błąd, że ścieżka już istnieje** — dodaj
  `--overwrite` (worker robi to automatycznie; przy ręcznym testowaniu
  `pac` pamiętaj o tej fladze).
- **Import `.msapp` nie pyta o ponowne podłączenie źródeł danych** —
  otwórz aplikację w Studio po imporcie → **Widok → Źródła danych** i
  ręcznie zamień każde źródło na listę we własnej witrynie (patrz Krok 4).
- **Zapis kolumny „Osoba lub grupa” przez Graph nie działa dla osoby,
  która nigdy nie odwiedziła tej witryny** — to oczekiwane: SharePoint
  dodaje użytkownika do ukrytej listy „Informacje o użytkowniku” dopiero
  po jego pierwszej wizycie na danej witrynie; worker po cichu pomija to
  pole zamiast przerywać zadanie, jeśli nie może znaleźć użytkownika.

---

## 13. Checklist końcowy

- [ ] `pac` CLI zainstalowany i zalogowany na docelowe środowisko
- [ ] Witryna SharePoint z 4 listami i biblioteką dokumentów utworzona i
      zweryfikowana (Krok 2)
- [ ] Rejestracja aplikacji Azure AD utworzona, uprawnienia Graph nadane
      ze zgodą administratora, sekret zapisany w lokalnym `.env` (Krok 3)
- [ ] Aplikacja Power Apps zaimportowana (lub zbudowana) i podłączona do
      **Twoich** list SharePoint, opublikowana i udostępniona (Krok 4)
- [ ] (opcjonalnie) Flow Power Automate zbudowane (Krok 5)
- [ ] `.env` workera uzupełniony wartościami produkcyjnymi (Krok 6)
- [ ] Test end-to-end na nieprodukcyjnym rozwiązaniu zakończony sukcesem
      (Krok 7)
- [ ] (opcjonalnie) Copilot skonfigurowany (Krok 8)
- [ ] Host, harmonogram i zasady bezpieczeństwa produkcyjnego ustalone
      (Krok 9, sekcja 11)

Powodzenia. Jeśli któryś krok nie zadziała dokładnie tak, jak opisano —
to prawdopodobnie dlatego, że coś w Twojej dzierżawie różni się od
dzierżawy testowej użytej do weryfikacji (region, licencja, wersja
konektora). Zajrzyj do `docs/POWER_PLATFORM_SETUP.md` i
`docs/SHAREPOINT_SETUP.md` po pełne, techniczne ustalenia z tej
weryfikacji — mogą wskazać, co dokładnie się różni.
