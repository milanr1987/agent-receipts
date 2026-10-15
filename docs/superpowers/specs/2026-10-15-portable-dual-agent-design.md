# Agent Receipts: prenosiva aplikacija za Codex i Claude

Datum: 2026-10-15. Status: objedinjeni dizajn za pregled prije implementacionog plana.
Prioritet: ovaj dokument zamjenjuje Codex-only obim. Izvorni dizajn ostaje izvor detaljnih zahtjeva gdje nije u sukobu s ovim odlukama.

## Namjera vlasnika i odluka o izgradnji

Vlasnik želi aplikaciju koju preuzme s Gita na drugi računar i koristi s Codex CLI i Claude Code. Želi pregled dokaza o izvršenju, upozorenja na oslabljene testove i opcionalne hookove. Posljednji zahtjev izričito traži brainstorming, plan i početak izrade za oba alata. To je promjena odluke da se ostane na Codex-only evaluaciji; izgradnja je eksperimentalna, a ne dokazano opravdana mjerenjem Faze 0.

Istorijski nalaz Faze 0 ostaje nepromijenjen: mali nerandomizovan uzorak 20 potkrijepljenih tvrdnji, 0 dokazano netačnih, 2 bez svježeg test runnera u istom potezu. To nije dokaz da alat nema vrijednosti za prenosivost ili testguard. Nema izmjene brojki, izmišljanja negativnih labela ili tvrdnje da je measured recall dokazan.

## Pristupi i izbor

1. Preporučeno: jedan Python 3.12+ CLI sa standardnom bibliotekom, adapterima formata i Markdown izvještajem. Jednostavno offline pokretanje i jedan skup pravila.
2. Dva nezavisna alata/pluginovi: manje početnog koda, ali postojeći isprobani alat ne čita Codex format; duplirana pravila i održavanje.
3. Web/desktop UI odmah: lakše vizuelno pregledanje, ali dodaje runtime, pakovanje i bezbjednosnu površinu. Odgađa se.

## Arhitektura

- ingest/claude.py i ingest/codex.py normalizuju događaje. detect.py prepoznaje format po podacima, ne samo ekstenziji.
- models.py definiše Event, Claim, Verdict, Session i dijagnostiku parsera. Sačuvati vremenski red, turn identitet, tool ID, rezultat komande i promjene fajlova.
- claims.py sadrži EN/BCS obrasce i listu runnera; ne klasifikuje citate, negacije ili buduće namjere kao završene radnje.
- evidence.py uparuje samo prethodne događaje. Nikada ne izvršava transkript kao kod. Zajednički algoritam ne zavisi od izvornog alata.
- testguard.py analizira stare/nove testove; Python preko AST, JS/TS preko označenih heuristika. Nalaz je signal, ne automatska presuda.
- report.py/redaction.py centralno redaktuju sve što ide u izlaz. cli.py koordinira audit, check-diff, eval i hook.
- discovery.py nalazi lokalne izvore u korisničkom home folderu ili po eksplicitnoj putanji; git_read.py je ograničen read-only subprocess sloj.

## Parsiranje i dokazi

Codex 0.162.1: primarno event_msg/item_completed CommandExecution (command lista, aggregated_output ili stdout/stderr, status, exit_code), FileChange, AgentMessage; turn_id/task_complete. response_item je rezerva uz deduplikaciju. Ne obraditi final poruku dvaput.

Claude: text/tool_use/tool_result i tool_use_id veza. Tool result nije nov korisnički potez. thinking se ne izvozi. Exit code parsirati samo kad postoji jasan strukturisan podatak ili obrazac; is_error=false samo po sebi ne dokazuje da su testovi prošli.

CONFIRMED znači prethodni konkretni dokaz za opseg tvrdnje. NO_EVIDENCE znači da provjera nije moguća ili nema dovoljnog dokaza; nije sinonim za laž. CONTRADICTED traži konkretan suprotan rezultat. tests_pass koristi zadnji završeni odgovarajući runner prije tvrdnje u istom potezu; ne prepoznaje čitanje dokumentacije s tekstom "pytest" kao pokretanje testa. Porediti broj testova i preskakanja kad ih tvrdnja navodi.

committed/pushed se oslanjaju na uspješne stvarne operacije i njihov rezultat, ne samo pojavu riječi u komandi. pushed potvrđuje istorijski događaj; trenutno stanje GitHuba ostaje neprovjereno. Bez ls-remote/fetch/mreže.

FileChange/Edit/Write dokazi moraju uključiti uspješan rezultat. Trenutno postojanje fajla ili trenutni Git log se jasno označava kao trenutna provjera; ne dokazuje automatski istorijsku tvrdnju.

## Granice runtimea

Samo čitanje sesija i projekata. Git: shell=False, timeout, GIT_TERMINAL_PROMPT=0, --no-optional-locks i bez naslijeđenih GIT_* preusmjeravanja. Ne pokretati Git write komande ili dodatne programe koje transkript navodi. Bez mreže tokom audita i bez novih zavisnosti.

CLI iz jednog check-outa:
- setup.cmd priprema lokalno Python okruženje bez mrežnog pip instaliranja.
- receipts.cmd audit [sesija] [--since 7d] [--source all|codex|claude] [--profile ime] [--project putanja].
- receipts.cmd check-diff --project putanja [--base HEAD].
- receipts.cmd eval eval/labels.csv.
- receipts.cmd hook --source codex|claude.

Pokretanje na Windowsu je primarno; Python modul radi i na drugim OS, a Windows cmd omotači to ne obećavaju. Nema korisničkih apsolutnih putanja u praćenom kodu. Skripte koriste vlastitu lokaciju i standardni Python 3.12+, ne Archify venv. Ako Python nedostaje, prikazati uputstvo; bez automatske instalacije sistema.

## Testguard i hookovi

Testguard obuhvata test_*.py, *_test.py, *.test.ts, *.spec.ts, tests/** i __tests__/**. Git diff mora očuvati i staged i unstaged promjene, rename/deleted fajlove i putanje s razmacima. Ne čitati proizvoljnu putanju izvan izabranog projekta i ne slijediti symlink izvan njega.

Pilot hookovi su warning-only za oba alata. Postojeći hookovi se čuvaju; generisati uputstva/primjere za ručno povezivanje. Protokol stdin/odgovora provjeriti u zvaničnoj dokumentaciji i lokalnoj verziji. Ne birati nasumični najnoviji transkript ako identitet sesije nije pouzdan. Greška ili nepoznat format propušta potez uz redaktovanu dijagnostiku; timeout 10 s, stop_hook_active sprečava ponavljanje. Blokada tek poslije izmjerenih lažnih alarma i posebne odluke.

## Privatnost

reports/, eval privatni podaci, .tools/, .venv/, .env* i raw sesije van gita. Redaction pokriva tokene, ključeve, privatne ključeve, e-mailove i korisnička imena u putanjama prije svakog upisa. Skenirani izvori se ne mijenjaju. Fixture su minimalne i redaktovane; pregled prije commita. Ne prenositi auth.json, kredencijale ili konfiguracije računa na novi računar preko repoa.

## Redoslijed i kriteriji

1. Prenosivi entrypoint, modeli, redaction i Codex parser sa lokalnim redaktovanim fixtureom.
2. Claude parser sa reprezentativnim fixtureima; status stvarne kompatibilnosti ostaje NEPROVJERENO dok nema stvarne redaktovane Claude sesije za validaciju.
3. Claims/evidence i eval za svih pet tipova; negativni i pozitivni testovi, bez budućih dokaza, bez grešaka u deduplikaciji i granicama poteza.
4. Testguard: 5/5 pokvarenih diffova; 5 legitimnih refaktora s dokumentovanim lažnim alarmima.
5. Read-only audit/report/discovery i prenosivi setup; test putanja s razmacima, pokretanje iz drugog cwd, bez promjene izvora/Git indexa i bez mrežnih poziva.
6. Dokumentovana warning-only integracija oba hooka; protokol i postojeći hookovi provjereni prije stvarne aktivacije.
7. Pet radnih dana upotrebe i 10 novih stvarnih labela. ≥80% precision/recall se ne proglašava bez pozitivnih/negativnih primjera; kalendarski pilot nije moguće završiti jednim testom.

Granica završetka izrade: testirani CLI, README i poznata ograničenja; odvojeno iskazati stvarnu Claude validaciju i kalendarski pilot. Nema tvrdnje da je aplikacija završena dok nedostaju obavezni elementi.

## Dalji proces

Ovaj dizajn čeka pregled vlasnika. Poslije odobrenja koristiti superpowers:writing-plans za konkretne fajlove, interfejse i testove, pa pregled plana prije implementacije. Podrazumijevani prijedlog je rad u jednoj sesiji bez delegiranja i dodatnih modela; finansijska pravila ostaju obavezna.
